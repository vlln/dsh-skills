# 实测坑（Gotchas）

> **本文件回答**：出现某个症状时，原因是什么、怎么修、依据哪个版本。
> **不回答**：纪律（→ [09-dev-conventions.md](09-dev-conventions.md)）、验证方法（→ [10-install-and-verify.md](10-install-and-verify.md)）、契约细节（→ [04-plugin-contract.md](04-plugin-contract.md) / [05-bundle-plugins.md](05-bundle-plugins.md) / [07-settings-panel.md](07-settings-panel.md)）。

**来源**：本 skill 的**实测层**（无官方对应文档）——机制契约以 [SKILL.md](../SKILL.md)「版本与权威来源」列的官方文档为准，这里只留"官方没写、只能踩出来"的部分。

**证据版本**：无标注的核实于 `0.1.5-rc.2`；标 `0.2.0-rc.2` 的为该版重核；`0.2.1` 未逐条重核。服务名、槽名、种子模块导出**每个 rc 都可能动**，跨基线时按条目标注重查。

## 症状索引

| 症状 | 去 |
|---|---|
| `npm install` 报 ERESOLVE / 官方包装不上 | §1 |
| `dsh plugin add git:…` 失败，提示 `allowBuilds` | §1c |
| 装完插件**整个 profile 起不来** | §6 |
| npm 版（`npx @deepseek-ai/dsh`）与源码版行为不一样 | §1d |
| 覆盖某行配置后，原来配的键丢了 | §1b |
| 插件显示已装，但工具/UI **静默消失** | §7 |
| `plugin tree failed to load` | §3 |
| 改了源码不生效 | §2 |
| 往会话写消息后**会话打不开** | §11 |
| `ctx.sessions.open()` 不存在 / 切不了会话 | §11 |
| 图标或控件取到 `undefined`、React minified #130 | §10 |
| 新页签上出现两条可拖动的竖线 | §12 |
| `/` 菜单里自己的命令没有图标 | §13 |
| 仓库里是 `.dsh-plugin` / `dsh-repository-plugin` | §1a |
| 从 ≤0.1.5 升级到 0.2.x | §8 |
| 插件条目不激活：`parameters must be an object of value schemas` | §14 |
| 按钮跑到了会话标题旁边 / 塞不进右上角 `···` 菜单 | §15 |
| `/plugins/<id>/client.js` 手测 404（插件明明在） | §21 |
| 设置卡写了但 Plugins 页上不出现 | §16 |
| 界面上出现 `blocked`、`summary` 这类字面量 | §17 |
| README 里视频不出来 / `<video>` 渲染成空白 | §18 |

## 1. 官方 SDK 的 peer 闭包与开发依赖

**历史实测**：`@deepseek-ai/dsh-tools@0.1.2-rc.1` 带多项官方 peer，单独用当时的 npm 安装曾报 ERESOLVE（`cordis` / `dsh-agent` 等版本冲突）。这证明要核对整组版本，**不证明所有 SDK、包管理器和版本都必然失败**。

**2026-11-03 静态复核**：近期插件采用两条路线——直接分发 JS、从宿主解析 SDK；或构建时 external 宿主模块、为开发类型/构建安装匹配的 SDK。来源及边界在 [16](16-engineering-patterns.md)，依赖规则唯一口径在 [05](05-bundle-plugins.md)「依赖解析」。本次没有重新运行这些插件的安装/测试。

本地 link 需要 SDK 时可在包自己的 `node_modules` 建开发链接，但不能覆盖既有真实目录；解析源从目标安装版现场取。开发 SDK 安装成功也不证明分发物在宿主里用的是正确实例。

- semver 预发布必须显式带后缀，普通稳定版范围未必接受 rc。
- 可选本地检查缺依赖可明确跳过并报告未验证；必跑 CI 的真实宿主测试缺依赖必须失败。
- 不能为迎合安装器把宿主 SDK 打成第二份内核/React；排查版本集合与解析路径，而非一概清空依赖。

### 1a. 看到 `.dsh-plugin` / `dsh-repository-plugin` 的仓库

那是**已删除的旧插件形态**（配套安装通道一并失效），不要照做——按 [05-bundle-plugins.md](05-bundle-plugins.md) 或纯 cordis 形态重写。原 repository 参考实现 `whale-girl` 已迁移为 bundle。

### 1b. bundle 的 patch 层语义

同名 `cordis.patch.yml` 出现在多个层，属主不同，写错层是 bundle 特有坑。生效顺序（后应用者按行胜出）：

| # | 层 | 位置 | 属主 | 用途 |
|---|---|---|---|---|
| 1 | 各组合包 patch | bundle 声明的一个或多个 patch 文件（`dsh.bundle.patch` 可为数组，按声明顺序拼接）；bundle 之间按 `dsh.profile.bundles` 顺序 | 产品开发者 | 组合行（插件声明；也可声明 `preset-<id>`） |
| 2 | profile 层 | `$DSH_HOME/profiles/<name>/cordis.patch.yml` | 用户 | insert 行 + 启停覆盖 |
| 3 | home 层 | `$DSH_HOME/cordis.patch.yml` | 用户 | 跨 profile 的机器本地偏好 |
| 4 | `--patch <path>` overlay | 按 argv 顺序 | 用户 | 一次性实验 |

两条语义：**按行 id 覆盖，替换整个 `config`（不是深合并）**——覆盖别人的行必须重述它需要的每个键；**bundle 启停覆盖写 profile 层**，不要写进 bundle 包内层。

层栈里还有 `preset-<id>`（`@deepseek-ai/dsh-agent-preset`）：同一套覆盖语义，但挂载的是**每个 Agent 的子树**——见 [02-profile-and-preset.md](02-profile-and-preset.md)。

**旧结论已撤回（0.2.0-rc.2 核对，0.2.1 复核）**：`patchReload` 不是永远不处理 bundle 层栈——`dsh-hmr` 会监视 profile manifest 的 bundles 列表并重读协调；0.2.1 起，**profile 重组还会替换磁盘上已变化的已加载插件（含 `node_modules`/link 目标）**，不要求 `root` 监听源码。是否生效取决于 HMR 是否启用（见 [10-install-and-verify.md](10-install-and-verify.md)）。

### 1c. git 源安装：`allowBuilds` 与四个坑

`dsh plugin --profile web add github:owner/repo#<ref>&path:/<子目录>`（或 `git+https://…`）安装时，pnpm ≥10 默认**阻止 prepare/build 脚本**。dsh 失败时会提示把 pnpm 打印的 key 加入 profile 的 `pnpm-workspace.yaml` 的 `allowBuilds` 后重跑。

1. **产物入库（推荐，真一行）**：`lib/` 提交进仓库、无 prepare——git 源安装不触发构建（console 实测 14s 装 + 挂载通过）。
2. **prepare 现场构建（备选）**：包带 `"prepare": "tsdown --config tsdown.config.ts"`（**别用 `pnpm run build`**——pnpm 在 npm 装的目录会触发 deps status check 循环失败）；按提示把 key 加入 `allowBuilds`。**key 含冒号，写 yaml 必须加引号**（无引号解析失败）。
3. **monorepo 子目录**：语法是 `#<ref>&path:/<子目录>`（`path:` 前缀 + 前导 `/`，漏写或写成 `&path=dir` 都失败）。
4. **Windows**：`dsh plugin` 经 cmd.exe 转发，`&` 是命令分隔符——`#<ref>&path:/…` 会被拆开（`ERR_PNPM_INVALID_DEPENDENCY_NAME`）。给用户的说明写**不带 `&`** 的 `#path:/<子目录>`（取默认分支 HEAD，跨平台）；需钉 commit 时在 profile 目录内直接 `pnpm add "github:…#<commit>&path:/…"` 再 `dsh plugin --profile web install`。

**`allowBuilds` 的安全语义要写进安装说明**：它允许该包**在安装时于用户机器上执行代码**，且不在 agent 沙箱内——只对可信源码放行，并建议用户钉 commit。另两条**不需要放行构建**的渠道：npm 预构建、tarball（见 [10-install-and-verify.md](10-install-and-verify.md)）。

### 1d. npm 版 dsh 与源码版观感不同

npm 上是 lib 生产模式（`npx -p @deepseek-ai/dsh@<版本> dsh web`）。实测差异：

- **bundle 生态兼容** ✓：console 的安装、`/installed` 合并枚举、启停全功能正常。
- **外部插件统一是 npm 包**（bundle / 纯 cordis）：repository 形态不可用（见 1a）。
- **"路由 200"不是挂载判据**：npm 版 `webServer` 对未匹配路由返回 200 SPA fallback（`__DSH_BOOT__` HTML）；源码版返回 404。看响应体，不看状态码。
- **代理坑**：npm/pnpm 走环境代理会超时卡死——装包用 `env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy` 直连（实测 519 包 2 分钟 vs 代理 10 分钟+）。
- **token 展开**：pnpm 项目级 `.npmrc` **不展开** `${NPM_TOKEN}`（凭据放用户级 `~/.npmrc` 或 `pnpm config set`）；npm 支持项目级 `${VAR}`。

## 2. 源码缓存 ≠ 宿主 HMR

"改源码后仍运行旧模块"只证明**当时环境**没完成热更新，不能推出"所有版本都必须重启"。0.2.1 核对：`dsh-hmr` 有两条路径——显式 `root` 的源码监听（`ignored` 默认排除 `node_modules`），以及 **profile 重组时替换磁盘上已变化的已加载插件**（覆盖 `node_modules`/link，无需 root）。先查 HMR 是否启用、是否触发过重组、产物是否重建、功能是否变化；不具备条件或替换失败（插件报 `failed`）时，**重启是兜底，不是安装说明的固定步骤**。配置协调、源码 HMR、client bundle 更新是三条不同路径（见 [10-install-and-verify.md](10-install-and-verify.md)「验证按改动面」）。

## 3. 挂载失败排查顺序

日志 `plugin tree failed to load` 时按序查：

1. `exports["."]` / `main` 指向不存在或无法解析的入口。
2. `inject` 未声明 `ctx.get` 用到的服务（严格注入抛错，见 §7）。
3. 依赖解析失败（见 §1 / §6）。
4. insert 行 `name:` 未加引号（YAML `@` 开头是保留指示符）。

## 4. 宿主全局 CSS 覆盖注入样式

宿主可能清理插件的 `<style>` 或用以更高优先级的类覆盖。**关键样式用 JS 内联**（内联优先级最高），不要依赖 class 注入。实例：插件状态卡/菜单按钮曾裸文字，改内联修复。首次踩到就写 bug-fix 决策记录并标「环境事实」。

## 5. 其它环境事实

- **client 必须经 `__ModuleLoader__.load` 注册**：client-modules 只扫描声明 `dsh.client` 的包；不注册报 `loaded without registering`。
- **严格注入**：`ctx.get` 未在 `inject` 声明的服务 → apply 开头抛 `cannot get property without inject`，整个 effect 不注册（路由全 fallback 成 SPA 主页）。
- **工具 schema DSL 违规在挂载时暴露**：CLI enable 只校验名称；`defineTool` 的 value-schema 违规在 web boot / 面板 enable 时暴露。

## 6. 安装位置影响 SDK 可达性（不能只看宿主是否启动）

官方包的解析源是 `$DSH_HOME/profiles/node_modules/`（含 `@deepseek-ai/*`）。ESM 从包的**真实路径**逐级向上找 `node_modules`：

| 安装形态 | 包的真实路径 | 结果 |
|---|---|---|
| git / npm / tarball | profile 管理的包目录 | 验证宿主解析与实际激活；不借开发目录补依赖 |
| 本地目录（树外 link） | profile 外真实目录 | 可能缺 SDK，需开发依赖/链接或改用分发物安装 |

```
dsh: plugin tree failed to load: failed to import loader entry <id> (<pkg>):
Cannot find package '@deepseek-ai/dsh-tools' imported from /abs/path/src/index.mjs
```

上面是早期整树失败的日志形状；0.2.1-rc.1 的后续记录也有「宿主正常启动、插件 `did not activate`」的形状（见 [10](10-install-and-verify.md)）。不要把一种错误表现当作跨版本保证。

**写安装说明**：已发布 npm 优先，其次已验证 git / tarball；本地 link 只作开发自测。**一种渠道能装不能反推另一种也能装**，真实分发物要单独验证。

## 7. 服务名跨 rc 漂移 → 静默功能死

官方服务名会随 rc 改名（实测 `workflows` → `workflowEngine`）。两种症状都阴：

- **用到却没声明 / 名字写错**（惰性读取）→ boot 完全干净、工具正常注册，**真调用**时才报 `no "<service>" service in this profile`。
- **声明了但宿主没有**（旧名字残留）→ 条目**永久 pending**，boot 日志只有 `warning: 1 entry did not activate`；功能与 UI 一起消失，只有启动面板列得出 `(waiting for service: <name>)`。

**核实方法**：以安装的基线为准，别照抄旧笔记——

```sh
grep -rn "workflowEngine" "$(dirname "$(readlink -f "$(command -v dsh)")")/../node_modules/@deepseek-ai"/*/lib/*.js | head
```

升级基线时把 `grep -rn "ctx.get('" src/` 当回归点。

## 8. 跨 rc API 换代表（≤0.2.0，升级既有插件时查）

旧名字**全都不报错**——症状只有"client 条目永久 pending"或"静默失效"。0.2.0-rc.2 复核：

| 旧（≤0.1.5） | 现行（0.2.0） | 症状 |
|---|---|---|
| `ctx.settings.register(ns, schema, { applies })` + `scope.get()/watch()` | 条目导出 `Config`（命名空间 = 条目 id）+ volatile 叶引用 + `loader/volatile-update` | 静默：配置页不出现、`settings.yaml` 的 `<ns>:` 不被读取 |
| client `inject: ['settingsScope']` / 槽 `settings.plugin.item` | `configForms` / `settingsSchema`；槽 `plugins.item` / `plugins.bundle.config` / `plugins.row.config` | 条目**永久 pending** |
| `ctx.jobs.onJobDone(cb)` | `ctx.jobs.events.subscribe({ owners }, cb)` 的 `settled` | apply 抛 `TypeError` → `1 entry did not activate` |
| `ctx.on('agent/session-start', ({ source }))` | `ctx.on('agent/created', ({ agent, source }))` | 静默：新会话记账不再触发 |
| `ctx.on('agent/disposed', (agent) => …)` | `({ agent }) => …`（payload 包了一层） | 静默：回调拿到 undefined |
| 消息 `source: { kind: 'plugin' }` | `{ kind: 'plugin:<插件名>' }` | 响亮：`format v4 message requires a producer-owned source kind` |
| `jobs.list(agent)` | `jobs.list(sessionId)` | 静默：按 agent 过滤恒不命中 |
| client `inject` 列 `@deepseek-ai/dsh-client-runtime` | 该包已不存在；种子表提供 `react` / `react-dom` / `dsh-client-store` / `dsh-client-ui-slots` / `dsh-client-ui-primitives` | 未知包名被容忍，但作为配方是错的 |

完整设置面配方见 [07-settings-panel.md](07-settings-panel.md)。核实方法：直接搜安装版源码，零命中即已移除。

## 9. 源码 / master ≠ 已发布 rc

官方文档与 checkout 跟 **master**，用户装的是**已发布 rc**；两者会不一致，且常在你最需要确定的那一格。实例（0.1.5-rc.2 时段）：

| 事实 | 发布版 0.1.5-rc.2 | 同时刻 master |
|---|---|---|
| `.credentials.yaml` 的 `version` | 要**数字** `1` | 要**字符串** `"1"` |
| headless 是否含 workflow 引擎 provider | **含**（`--dump-config` 可见） | — |
| `dsh web --no-open` | **没有**该 flag | — |

**更新**：`--no-open` 在 **0.2.1 已存在**（`dsh web --help` 实测）——这条正好说明为什么过期结论不能默认成立。

**纪律**：结论绑定版本号；与文档冲突时以**安装的运行时**为准并把差异写回来；验证用**安装版 dsh**——直接跑源码 checkout 在隔离 `DSH_HOME` 里会因 `profiles` 层镜像的是安装目录依赖而集体解析失败，**极易误判成自己的插件坏了**。

## 10. 平台种子模块导出名会随 rc 改（图标/控件取到 undefined）

平台注入给 client bundle 的是**静态模块表**（0.2.0 叫 `getStaticModules()`；0.2.1 安装版的类型里是 `staticModules` 字段）——**导出名不保证稳定**。0.2.0 实测：图标是 `<Name><Regular|Medium>` 后缀（`IconRefreshOutlineRegular`），旧写法 `IconRefreshOutline16` 已不存在——`require()` 取到 undefined **导入时不报错**，渲染时才炸：

```
slot entry crashed in '<slot 名>' + Minified React error #130
```

整个槽静默失效（同 bundle 的其它槽可能照常）。**纪律**：`require` 解构出的名字先在应用 bundle 里核实存在；升级基线时当回归点重扫（`grep -o "Icon[A-Za-z]*" src/client/*.tsx`）。0.2.0-rc.2 种子表：`react`、`react/jsx-runtime`、`react-dom`、`react-dom/client`、`@deepseek-ai/cordis`、`dsh-client-store`、`dsh-client-ui-slots`、`dsh-client-ui-primitives`、`dsh-client-ui-dockkit`。

## 11. 往会话写消息：v4 硬要求 + 会话导航

写消息（注入上下文、合成 `assistant/message`、写 `tool/result`）时，v4 校验会拒绝旧形状——**症状不总在写入点**：有的当场抛，有的等**下一次读取**才炸，那时会话已经打不开。

| 要求 | 旧写法 | 现行写法 | 后果 |
|---|---|---|---|
| `source.kind` 是**生产者自有** kind | `{ kind:'plugin', plugin:'X' }` | `{ kind:'plugin:X' }`（或自有 kind，如 `fork-answer`） | 响亮：`format v4 message requires a producer-owned source kind` |
| `assistant/message` 必须带 `stream` | 无 | `stream: []` | **会话打不开**：`has invalid settlement fields` |
| `tool/result` 的 message | `role:'user'`、无顶层 `toolCallId` | `role:'tool'` + 顶层 `toolCallId` | 采用校验拒绝 |

判据来源：`dsh-session-format-v3-to-v4` 的 `assertV4MessageSources` / `rewriteV3MessageSource` / `producerKind`、`dsh-session` 的 `assertAssistantSettlementShape`、`dsh-llm` 的 `MessageSourceMap`（注释明说没有共享 `plugin` 兜底 kind）。

**会话导航**：0.2.0 起从 `ctx.sessions.open()` / `openSubagent()` 换成 **`ctx.uiWorkspace.openSession(target)`**（`target` 是 session id 或 durable 子会话地址）；inject 里加 `uiWorkspace`。

## 12. 新 `conversation.view` 页签继承「对话」页签的宽度手柄（0.2.0-rc.2）

**现象**：自建页签上出现两条竖线、悬停变 `col-resize` 还能拖——那是「对话」页签调转写宽度的外壳手柄。

**机制**：页签共用会话内容区，手柄由外壳渲染、不属于任何视图：

```
[data-conversation-region=content]      ← 各页签共用
├── [data-conversation-scroll]          ← 当前视图内容（你的页签在里面）
├── div[data-width-handle=left]         ← 外壳手柄（兄弟姐妹）
└── div[data-width-handle=right]
```

来源是 `dsh-client-ui-conversation` 的 `ConversationWidthControls`（factory 槽 `widthControls`）：`container === null || phase !== "active"` 时返回 null，其余一律渲染。

**正解**：给视图根元素挂稳定属性（如 `data-myplug-view`），再在样式里：

```css
:has([data-myplug-view]) [data-width-handle]{display:none}
```

前提已实测：切页签时另一视图会卸载，所以 `:has()` 只在你的页签挂载时成立。

**两个坑**：不要写 `:has(> [data-myplug-view])`（视图是共享区域的孙节点，`>` 匹配不上）；不要锚官方 CSS module 的哈希类名（`wSkVaW_widthHandle`）——`[data-width-handle]` 才是稳定属性，官方自己也用 `:has()` 隐藏它。**别顺手藏 composer**（输入框座在任何页签都有意义）。

## 13. `/` 菜单命令行外观：宿主命令没有注册入口（0.2.0-rc.2 / 0.2.1）

**现象**：`ctx.commands.register(...)` 的宿主命令在 `/` 菜单里只有裸命令名 + description；没有图标，也没有本地化标题（中文用户输入「循环」搜不到 `/loop`）。官方 `/goal`、`/compact` 都有图标 + 本地化标题（中文界面下还会显示灰色 name 别名）。

**机制**：行外观不在宿主侧——`CommandDescriptor` 只有 `{ definitionId?, name, description, input? }`；`label` / `icon` 出自客户端 `dsh-client-ui-commands`。内置行从 `presentation.ts` 的硬编码表 `HOST_FACES`（goal / plan / feedback / compact / permission / export）按 `definitionId` 命中；第三方宿主命令命中不了。`label` 缺失时菜单按 `label ?? name` 显示裸名；label 是候选层的第二个搜索键（输出贴面见下）。

**三条别试**：同名注册客户端贡献 → `contribution /x collides with a host command`，**整组「指令」一起消失**；`ctx.commandUi.decorate` → 契约里没有 `label` / `icon`；给描述符塞 `label` / `icon` → 宿主侧没这些字段。

**两条可行路**：① 接受官方回退外观（裸 name + description，无图标、无本地化标题）；② 要行外观就把命令做成**客户端自有贡献**（`ctx.commandUi.register({ …, label, icon })`，失去带参形式与宿主生命周期记账），或在 `commandUi.candidates` 出口**只贴自己那一行**的 `label` + `icon`——注意 `candidates` 在 0.2.1 的类型里是 **private**，这是登记在案的越界，必须按 [06-ui-style.md](06-ui-style.md) §10.7 的自降级包装写法（服务缺席/改名时静默回落），参考 `vlln/dsh-loop` 的 `installCommandRowFace`。**只贴 icon 不贴 label** 是常见漏项：行标题仍是裸命令名。

**贴面只修显示，不修搜索**：`rankByName` 在 `candidates` 内部、贴面之前运行；贴出来的 `label` 不参与查询，`/循环` 这类只命中 label 的查询仍为空。要让本地化标题可搜，只能用客户端自有贡献/源。

## 14. `defineTool.parameters` 是「属性名 → 值 schema」的普通对象（0.2.1-rc.1）

**症状**：插件装上了但整个条目**不激活**，boot 日志一行：

```
dsh-share-link (@vlln/dsh-share-link): JsonSchemaError: unsupported JSON schema: parameters must be an object of value schemas
```

**原因**：`defineTool({ parameters })` 要的是 JSON-Schema 形状的**属性映射**，不是 schemastery 对象。
传 `Schema.object({...})` 会得到 `{ type: 'object', properties: {...} }`，被当成"某个参数的值 schema"，
编译器要求每个 value 都是值 schema 时直接抛错。

```js
// ✅
parameters: {
  path: { type: 'string', required: true, description: '…' },
  ttl_hours: { type: 'number', description: '…' },
}
// ❌ 整个条目不激活
parameters: Schema.object({ path: Schema.string() })
```

空参数写 `{}`。`Config`（设置命名空间）仍然用 schemastery，两者不是一个东西。

**判据**：`boot` 里出现 `did not activate` 就先把 `parameters` 换回属性映射再猜别的。

## 15. 会话 header：`.actions` 在标题旁，`.utilities` 才是右上角；而且**没有菜单项插槽**（0.2.1-rc.1）

**症状 A**：插件注册进 `conversation.session.header.actions`，按钮却出现在**会话标题右边**
（`titleRow → titleCluster` 里），而不是右上角那一排。
**症状 B**：想把功能塞进右上角 `···` 菜单，翻遍 slot 名找不到入口。

实测布局：

| 槽 | 实际位置 |
|---|---|
| `conversation.session.header.actions` | 标题集群内（跟着标题走） |
| `conversation.session.header.utilities` | 右上角：token 徽章、`···` 菜单、自定义图标 |

`···` 菜单本身由 `dsh-session-log-export` **自渲染**（`Download session log` / `Feedback`），
宿主只给了 `sidebar.*.menu.item`，**没有**会话 header 的菜单项槽。

**能接受的做法**：在 `header.utilities` 注册自己的图标（兜底入口），再用 MutationObserver 在
`[data-slot="conversation.session.header.utilities"] [role="menu"]` 出现时**克隆一个既有菜单项**
改文案/图标——克隆能拿到完全一致的内边距、hover 与焦点样式，不用猜 hash class。要点：
守卫（已注入就不再注入，避免自触发循环）、跟随宿主语言、点击后先 `Escape` 关菜单再开自己的对话框、
**失效必须静默降级**（按钮兜底仍在）。

**判据**：这是版本敏感的做法，跨 rc 先看菜单 DOM 是否还是 `role="menu" + role="menuitem"` 结构。

## 16. `plugins.bundle.config` 的 `key` ≠ 设置命名空间（0.2.1-rc.1）

**症状**：卡片代码跑了、`whileServed` 也进了，Plugins 页上就是不出现，**没有任何报错**。

`key` 要等于 **`package.json` 的包名**；`configForms.get(ns)` / `whileServed([ns])` 用的是**条目 id**。
scoped 包（`@scope/name`）下两者必然不同名，别为了"同名"去改条目 id。细节见
[07-settings-panel.md](07-settings-panel.md) §1 与 §3。

## 17. 客户端字典缺键时 `t(key)` 返回**键本身**（0.2.1-rc.1）

**症状**：英文界面里按钮显示 `blocked`、卡片副标题显示 `summary`——不是报错，是缺键。

`ctx.locale` 的 `t()` 找不到键时回落成键字符串，不是 `undefined`，所以
`tr('blocked', '中文兜底')` 这种"有兜底"的写法**永远不会走兜底**。

**纪律**：新增键必须同时补 `zh` 与 `en`；要兜底就自己判 `t(key) === key`。

## 18. README 里的视频：`<video>` 会被剥掉，只有 `user-attachments` 出播放器（0.2.1-rc.1）

**症状**：README 写了 `<video src="docs/demo.mp4" controls>`，页面上什么都没有（HTML 里是空 `<p>`）；
换成 `<video src="https://…/user-attachments/assets/…">` 也只是个链接。

**原因**：GitHub 的 markdown 渲染器直接过滤 `<video>` / `<iframe>`。播放器只对**上传产生的**
`user-attachments` 资源生效——渲染结果是 `<details … device-camera-video>` + `<gh:secured-asset-reference>`。

**怎么造那个 URL**：`gh` ≥ 2.99 的 `--attach`（只挂在 issue / PR 的 create / edit / comment 上，**没有 discussions**）：

```sh
gh issue create --repo OWNER/REPO --title "temp: media" --body '![](docs/demo.mp4)' --attach docs/demo.mp4
gh issue view <n> --repo OWNER/REPO --json body --jq .body    # 拿 URL
gh issue delete <n> --repo OWNER/REPO --yes                   # 附件不随 issue 删除，URL 仍 302
```

然后把 URL **裸写一行**（别包标签、别放句子里，行内会退化成链接）。

**判据**：`curl -I <url>` 应 302 到 `….s3.amazonaws.com/….mp4`；再用 `/markdown` API 渲染一次确认出的是
播放器组件而不是 `<a>`。完整流程与大小上限见 [11-publish.md](11-publish.md)「README 首屏」。

## 19. 原生右侧栏页签条：chip 几何与「关闭邻居」都属于宿主（0.2.1-rc.2）

**症状**：插件自己的页签条已经等宽，但用户看到的「文件页签」在 **DSH 原生右侧栏**顶部——宽度仍跟着标题走
（`README.md` 窄、`sidebar.module.css` 宽），每个 × 不在同一列；右键菜单只有「关闭」，没有「关闭其他 / 左 / 右 / 全部」。

**归属**：那条条带由宿主的 docking kit 渲染，插件只通过 `sidebar.right.pane.tab.title` 贡献 chip 内容。
chip 几何是宿主 CSS：`.tab { flex: 0 1 auto; min-width: 80px; max-width: 170px }`；行是
`.stripTabs { flex: 0 1 auto; overflow-x: auto }`，旁边还有 `.stripFill { flex: 1 1 0 }` 占位；× 是
`position: absolute; right: 4px; opacity: 0`，**hover 或该 chip 激活时才出现**。

**等宽（实测可行的最小面）**：三条声明，锚**稳定语义属性**（宿主自己的布局代码也读它们——
`measure.ts` 的 chip 尺寸、`data-dockkit-tab-clipped` 的截断检测都靠这些属性），不点 hash 类名、不用 `!important`：

```css
[data-sidebar-right-panel] [data-dockkit-strip-tabs] { flex: 1 1 0; } /* 行吃掉条带余量 */
[data-sidebar-right-panel] [data-dockkit-strip-fill]  { flex: 0 0 0; } /* 否则占位与行对半分 */
[data-sidebar-right-panel] [data-dockkit-tab]         { flex: 1 1 0; } /* 等分；80/170 不变 */
```

三个坑，都实测过：① **只改 chip 不够**——行是内容宽的，页签簇不会去吃条带余量（2 个页签停在 115 而不是 190）；
② **忘了让 `strip-fill` 让位**，它会和行对半分余量（宽条带下页签簇只占左半边）；③ **作用域必须带
`[data-sidebar-right-panel]`**——浮动窗的浮层头复用同一批类（`.tab.floatTitle` / `.stripFill`）但没有这两个属性。
失效模式是**静默**的：宿主改名或换布局模型后选择器不再匹配，chip 退回宿主自己的内容宽，不报错也不破版式——
这正是这类耦合可接受的降级形态。两条属性选择器（0,2,0）压过宿主的单类（0,1,0），所以**与样式表注入顺序无关**。

**关闭邻居**：宿主给了公开槽 `sidebar.right.tab.menu.item`（list，owner 只有 `{ tab, dismiss }`），但
`TabRecord` 只有 `{ id, kind, contentId, title }`、`tabsIn()` 是 `Object.values(layout.tabs)` ——
**没有 pane、也没有条带顺序**。要按条带作用域就得自己从 chip 读：`[data-dockkit-tab]` ⊂
`[data-dockkit-strip-tabs]`，分屏是两个 strip，所以用**被点 chip 的 `closest()`**；**解析不到就一行都不渲染**
（kit 自己的「关闭」仍在 → 不会出现死行；**绝不要退回会话级**——那会关掉另一栏的页签）。
关闭动作走 `ctx.sidebarRight.close(tabId)`：它对不可关闭的页签（唯一的 docked guide）是 no-op
（`closeIn` 的 `canCloseTab` 守卫），所以「关闭全部」不会把栏关空。行样式复刻 kit 的 `.menuItem` 量度
（`padding: 4px 7px`、`13px - 1px`、`--dsw-radius-md`），因为它渲染在 kit 的 `<div role="menu">` 里，而菜单项**没有导出件**。

**关闭时冻结宽度（Chrome 的"指针还在条带上就不重排"）**：宿主**在关闭页签时会重建条带的 DOM**——实测
`[data-dockkit-strip]` 节点被整个换掉，所以"挂在条带元素上的属性 / 挂在它上面的 MutationObserver"会在最需要
它的那一刻失效。可用的形状：状态挂 **`<html>`**（`data-dsh-tabs-frozen` + 一个 CSS 变量），由**关闭手势**
（`pointerdown` 落在宿主的 `[data-dockkit-tab-close]`、或中键按在 chip 上）触发，量的是**关闭前**的宽度；
释放按"指针是否还在那条带"判定——注意关掉被 hover 的 chip 时浏览器发的是 **`relatedTarget: null` 的
`pointerout`**，把它当成"离开"会当场解冻，需要延后一个 task 用 `elementFromPoint` 复核。
**判据**：DevTools 里 chip 有 `data-dockkit-tab`、行有 `data-dockkit-strip-tabs`、面板有 `data-sidebar-right-panel`；
这些属性哪天消失，上面的 CSS 与菜单行会一起静默失效。参考实现：`vlln/DSH-better-sidebar` 的
`src/client/layout.css`（三条声明）与 `src/client/native/tab-menu.tsx`（四项 + `stripOrderOf`）。

## 20. 真机挂载才抓得到的两类"全绿也炸"（0.2.1-rc.1 实测）

单测/mock ctx 全绿、构建通过、页面也不报错，但功能就是不动。两个真实案例（同一次独立实例验证里连中）：

**① `list` 槽必须给 `options.id`**（keyed 给 `key`，chain 给 `select`）。只写
`ctx.slots.register({ name: 'sidebar.right.tab.menu.item' }, Component)` 会在真实 registry 上抛
`list slot "…" requires options.id`——而 mock ctx 如果只镜像 `name`，这条永远测不出来。
修法：`register({ name, id: 'my-plugin:that-entry' }, …)`；同时把假 ctx 升级成**会拒绝无 id 的 list 注册**，
并加一条「注册确实带 id」的正向断言（否则下次还会漏）。

**② `@media` 块没闭合 → 它之后的每条规则都死**。浏览器在 EOF 隐式闭合未闭合的块，于是
"语法合法、构建通过、单测全绿"，而实际渲染里那批规则只在该 media 条件成立时才生效
（本例是 `@media (prefers-reduced-motion: reduce)` 吞掉了子面板翻转/贴靠与随后新增的 chip 等宽规则，
**从 v0.26.0 一路发到 v0.28.0**）。

**判据（唯一可靠的）**：真机里 `getComputedStyle(el)` 读你要改的那条属性。页面里存在我们的 `<style>`、
规则文本在 bundle 里 → 都不算证据。样式改动排查顺序：
`getComputedStyle` → 若没命中，先看 `document.styleSheets` 里规则有没有被**解析**（`cssRules` 条数远少于预期 =
文件里有块没闭合/有语法错误）→ 再看选择器特异性与加载顺序。

**根因预防**：给样式表加一条"块结构"测试（花括号配平 + 关键块只含它该含的规则），
拿掉那个 `}` 就当场红；并在验证表里把「样式/布局」单列一行（见 [10-install-and-verify.md](10-install-and-verify.md)「验证按改动面」）。

## 21. 插件 client bundle 的手测 URL 带两个问号（`??`）（0.2.1-rc.5 实测）

旧检查点曾写「`/plugins/<id>/client.js` 200」——0.2.1-rc.5 上这个形式直接请求是 404；入口与清单已改为取页面中的完整 URL。
真实形式里 `?` 是**两个字面字符**（`??` 是 client-modules 的 URL 编码约定，不是笔误）：

```text
/plugins/??<包名>/client.js&rev=<启动时算出的修订号>
```

正确的打开方式（不要手拼 rev）：从页面里取现成的——
`curl -b <cookie> http://<host>/ | grep -oE 'plugins/\?\?<包名>/client\.js&rev=[a-f0-9]+'`，
然后**原样**请求那个 URL（含字面的 `??`）。`/plugins/<包名>/client.js?rev=<同值>`（单问号）404，
少 rev 也 404——路由要求 URL 与广告值逐字符相等。官方包的 client.js 同样如此，
所以这不是你的插件的问题，是这条检查点的写法在该版本上整体如此。

核对 2026-11-02（dsh 0.2.1-rc.5，隔离实例实测：单问号 404、无 rev 404、双问号原样 200）。
