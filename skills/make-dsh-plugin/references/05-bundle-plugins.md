# Bundle 插件开发详情（dsh.client 包）

> **本文件回答**：bundle 形态、`dsh.bundle.patch`、依赖解析、安装渠道写法。**不回答**：preset 声明（→ 02）、市场索引（→ 12）。

**来源**：官方 `docs/user/develop/basic/config.md`（插件配置 / 打包 / 安装）、`basic/publish.md`（四条发行渠道）、
`apps/cli/reference/README.md`（层栈 / profile / CLI 行为）；peer 门槛、git 源语法与其 Windows 坑为**实测**
（版本标在各条内）。基线 **0.2.0-rc.2**（2026-10-15 核）；**0.2.1-rc.1 复核**：`dsh.bundle.patch` 数组、peer 门槛与 `includePrerelease`、`must not declare its own package in dsh.client.external` 错误文本、`tsconfig.base.client.json` / `packages/client/tsdown.client.ts` 路径均成立。复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

两种插件形态之一：bundle = 声明 `dsh.bundle.patch` 的 npm 包（自带一层组合 patch），经 profile 层栈安装；与纯 cordis 插件（装完在 `cordis.patch.yml` 写 insert 行）互补。选型见 SKILL.md Step 0 形态表。本文件是 make-dsh-plugin 的自带参考（独立分发不依赖仓库 docs）。

## 形态

bundle 插件是**独立 npm 包**（或包目录），声明 `dsh.bundle`：

```json
{
  "name": "my-bundle",
  "version": "0.1.0",
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } },
  "exports": { "./client": "./client/index.js" }  // dsh.client 通道（可选）
}
```

- **`dsh.bundle.patch`**：指向组合行声明（`cordis.patch.yml`——定义该 bundle 挂载哪些插件 id）；也可以是**有序数组**，多个 patch 文件按序拼接（官方 `@deepseek-ai/dsh-web-app` 就是 `["cordis.patch.yml", "presets/standard.patch.yml", …]`，一个包同时分发宿主行与 4 个 agent preset）
- **`exports["./client"]`**：`dsh.client` 通道（浏览器端 bundle 进 `__DSH_BOOT__`）——官方静态 client 通道

要分发**新的 Agent 模式（preset）**时，patch 里 insert 一行 `preset-<id>`（`@deepseek-ai/dsh-agent-preset`）即可，写法和覆盖语义见 [02-profile-and-preset.md](02-profile-and-preset.md) §2。

## cordis.patch.yml（组合行声明）

```yaml
# my-bundle：向组合挂 Node half（命令/工具/路由）
- insert:
    - id: my-bundle
      name: 'my-bundle'
```

插件本体仍是完整 Cordis 插件（`apply(ctx)` + `defineTool` 等）。

## 开发

- **Node half**：标准 Cordis entry（`name`/`inject`/`apply` + `defineTool` 注册工具 + 服务/事件/命令）
- **client**（可选）：`__ModuleLoader__` 契约的浏览器 bundle（经 `exports["./client"]` 进 `__DSH_BOOT__`），或自渲染（`apply(ctx)` 内直接操作 DOM）
- **构建**：`tsdown` 或官方 client preset——Node half 产物 + client bundle 产物

## 依赖解析

- `dependencies` / `peerDependencies` / `devDependencies` **三处都留空是设计**——`@deepseek-ai/*` 与 `cordis` 由 profile 的 pnpm 闭包在挂载时注入（`$DSH_HOME/profiles/node_modules` 扁平 fallback；launcher 另把一份不可变 runtime resolution 装进 Node resolver，机制见 [02-profile-and-preset.md](02-profile-and-preset.md) §1.5）
- **不要声明官方包**：它们在公共 npm 虽可见，但自带整条 peer 闭包，单独安装必然 ERESOLVE 失败（理由、semver 预发布坑与本地 link 配方见 [13-gotchas.md](13-gotchas.md) 1）
- 解析可达性取决于**安装位置**：只有装在 profile 树内的包能向上找到那个 fallback（见 [13-gotchas.md](13-gotchas.md) 6）
- 本地开发要跑插件代码时，把 SDK link 进**该包自己的** `node_modules`（配方见 [13-gotchas.md](13-gotchas.md) 1），再按下面的「本地目录」安装

**dsh 的 peer 门槛（会直接拒挂载）**：宿主只校验 `@deepseek-ai/dsh` / `@deepseek-ai/dsh-*`
开头的 peer，用 `semver.satisfies(runtime, range, { includePrerelease: true })`；不满足就
`dsh: skipping profile bundle "<pkg>"` 并整包不挂载（面板可见、功能全无）。两个可用写法：

- `workspace:^` / `workspace:~` / `workspace:*`——**语义是「当前运行时」**，永远兼容
  （想跟随挂载环境又不被 rc 线卡住时用它）；
- 显式范围——预发布要显式出现在范围里（如 `^0.2.0-rc.1` 才接受 `0.2.0-rc.2`；
  写 `^0.1.0-rc.6` 上界排除 0.2.0，即使 `includePrerelease` 也救不回来）。

## 创造模式：在产品里直接做 bundle（可选路径）

Web 的 **创造模式**（`cordis` preset）就是 dsh 自带的"做插件"通道：它给 Agent 一组随运行时发布的
skills（`cordis-plugin-development`、`editing-cordis-compositions`、`cordis-composition-reference`、
`agent-experience`），以及只读的 `plugin_market` 与 `plugin_manager` 工具。

**怎么进**：Plugins 页 →「添加插件」旁的箭头 → **让 Agent 创建插件**；或在设置/新任务里选「创造模式」（列表里没有 `cordis` preset 时，这个入口不出现）。
进入后 Agent 在**工作区**里写一个 bundle 目录，再用 `plugin_manager` 的 `install_bundle`
装进当前 profile——不需要仓库、不需要发布、装完即刻可用。

这四份 skills 是**产品内的权威**（`cordis-plugin-development` 写插件/页面/设置卡、`editing-cordis-compositions` 写/改 preset、`cordis-composition-reference` 讲 patch 方言与可装包、`agent-experience` 讲工具描述与上下文加载）；它们只在创造模式挂载，内容随运行时版本。**本 skill 不复制它们**，只负责仓库化与分发。

| 你想做 | 产品内权威（创造模式） | 本 skill 的对应篇 |
|---|---|---|
| 加工具 / 页面 / 设置卡 | `cordis-plugin-development` | [04](04-plugin-contract.md) · [06](06-ui-style.md) · [07](07-settings-panel.md) |
| 写 / 改 preset、组合 YAML | `editing-cordis-compositions` · `cordis-composition-reference` | [02](02-profile-and-preset.md) · [03](03-vertical-agent-recipe.md) |
| 工具描述 / 上下文体验 | `agent-experience` | [04](04-plugin-contract.md) · [06](06-ui-style.md) |
| 打包、分发、README、验证 | —（不在产品内） | [05](05-bundle-plugins.md) · [10](10-install-and-verify.md) · [11](11-publish.md) |

**什么时候用它**（优先）：

- 一次性 / 个人本机 / 只想给当前 profile 加个能力；
- 原型阶段：先确认"这个工具/界面到底长什么样"，再决定要不要产品化；
- 想用**与当前运行时版本一致**的 API 知识——它的 skills 随 dsh 安装发布，天然对得上。

**什么时候改用本 skill 的仓库路径**：

- 要**分发**（git / npm / 市场索引）或给团队用；
- 要有包契约（`dsh.client`、icon、locale、peer 门槛）、README、兼容性表、门禁与决策记录；
- 要跑多 profile / 多宿主（web + Desktop）验证，或需要可回归的测试。

**边界**：`install_bundle` 会把代码装进 Host 进程，**需要 Full access 或逐次批准**；装的是**当前 profile**，
影响该 profile 的所有会话，不是沙箱。它也不替你产出 README、版本号、测试与发布物。

**从创造模式交接到仓库**（原型 → 产品）：

1. 把工作区里的 bundle 目录搬进独立仓库（`package.json` + `cordis.patch.yml` + entry + client）；
2. 按 [04-plugin-contract.md](04-plugin-contract.md) 补齐 `dsh.bundle.patch` / `dsh.client` / `icon` / `locale`；
3. 按 [templates/README.md](../templates/README.md) 写 README，按 [09-dev-conventions.md](09-dev-conventions.md) 加门禁与决策记录；
4. 用 **git 源**重装一次验证（[10-install-and-verify.md](10-install-and-verify.md)），而不是继续用 workspace 安装；
5. 升级 dsh 时按 [13-gotchas.md](13-gotchas.md) 重核服务名/槽名。

## 安装与管理

> 市场索引（「发现」页）只是**发现渠道**：它列出 npm / git 来源与版本，安装仍走这里的普通通道并再校验兼容性（见 [12-ecosystem.md](12-ecosystem.md) §B）。

**安装**：`dsh plugin --profile web add <包路径>`——`<包路径>` 必须是**可解析的 npm 包**：

- **本地目录**：指向**含 `package.json#dsh.bundle` 的 bundle 包目录**（而非仓库根或源码目录），且**构建产物在库**（`lib/` 等 `files` 声明的内容已 build）：
  ```sh
  cd packages/my-bundle && dsh plugin --profile web add .   # 包目录内 add .（dsh 锚定 . 为绝对路径）
  ```
  ❌ 不要写仓库根（`dsh plugin --profile web add ./`）——根不是 npm 包，无 `dsh.bundle`。
  ⚠️ **零依赖包的本地目录装有一个前置条件**：包的真实路径必须在 profile 树**外**时，官方包解析不到（Node 从包的真实路径向上找 `node_modules`）⇒ 装载期抛错、**整个 profile 起不来**。所以本地试装前先把 SDK link 进该包 `node_modules`（[13-gotchas.md](13-gotchas.md) 1），再按上面命令 add。**面向用户的安装说明只给 git 源**——别把裸的 `add .` / `add <绝对路径>` 写进 README（[13-gotchas.md](13-gotchas.md) 6）。
- **git 源**：官方经 npm git 依赖语法解析（`github:owner/repo#<commit>&path:/<子目录>`、`git+https://github.com/owner/my-bundle.git#<commit>` 等 pnpm 语法均可用）。bundle 在 monorepo 子目录时用 **`#<commit>&path:/<子目录>`**（注意 `path:` 前缀 + 前导 `/`，实测 plugin-registry 的 console 即 `github:vlln/plugin-registry#main&path:/packages/plugin/console`）。**产物入库是推荐做法**（`lib/` 等构建产物提交进仓库，`files` 声明）——git 源安装不跑构建，产物直接可用，**真一行安装**（`dsh plugin --profile web add "github:owner/repo#ref&path:/packages/my-bundle"`，无额外步骤）。**产物不入库的备选**：带 `prepare` 脚本（如 `"prepare": "tsdown --config tsdown.config.ts"`）让 git 安装时自动构建——但 pnpm ≥10 默认阻止 git 依赖的 prepare，需按 dsh 提示把精确 key（**写入 yaml 时加引号**——含冒号，无引号 YAML 解析失败）加入 profile 的 `pnpm-workspace.yaml` `allowBuilds` 后重跑（多一步交互）。
  ```sh
  dsh plugin --profile web add "github:owner/my-bundle#<commit>&path:/packages/my-bundle"
  ```
  ❌ 不要写未构建且无 prepare 的 git 源（缺产物挂载失败）；`git+file://` 本地可达但不是分发形态（对远端用户不可用），别写进安装说明。
  ⚠️ **Windows**：`dsh plugin` 在 win32 经 cmd.exe 转发参数，`&` 是命令分隔符——`#<commit>&path:/...` 会被拆开而失败（`ERR_PNPM_INVALID_DEPENDENCY_NAME`）。**给用户的安装说明应写不带 `&` 的 `#path:/<子目录>` 形式**（pnpm 原生语法，取默认分支 HEAD，实测 plugin-registry console 即 `github:vlln/plugin-registry#path:/packages/plugin/console`，跨平台可用）；需钉分支时 POSIX 用 `#<commit>&path:/...`，Windows 用户在 profile 目录内直接 `pnpm add "github:...#<commit>&path:/..."` 再 `dsh plugin --profile web install`（绕开 dsh 转发）。

- **两条不需要构建授权的渠道**：**npm 预构建**（`pnpm publish` 时构建好 `lib/`，用户 `dsh plugin add <pkg>` 拿到产物）与 **tarball**（`pnpm pack` 出包，用户 `dsh plugin add ./x-0.1.0.tgz`）。
- **`allowBuilds` 的安全语义要写进安装说明**：放行 = 允许该包在安装时于用户机器上执行代码，且不在 agent 沙箱内；只对可信源码放行，并建议钉 commit（细节见 [13-gotchas.md](13-gotchas.md) 1c）。

**写安装说明时**（README/skill 输出）：给出**用户能直接复制执行**的命令——本地路径写清 bundle 子目录与构建前提；git 源写清子目录语法（`&path:/`）、prepare 构建与 `allowBuilds` 放行；按目标运行时验证生效条件，不默认附加重启要求。不要给「指向仓库根」「裸本地目录」或「臆造协议」的说明。

- **启停/多层归属**：同名 `cordis.patch.yml` 出现在多个层（bundle 包内声明 / profile 层 / home 层 / `--patch` overlay）别写错层，见 [13-gotchas.md](13-gotchas.md) 1b

## 验证

- 挂载后 boot graph 含 bundle id；`/plugins/<id>/client.js` 200（若带 client）
- 改 Node half 源码：默认**不假设重启**——先按 HMR 条件验证（[13-gotchas.md](13-gotchas.md) 2）；不具备条件时重启兜底
- 改 client bundle：先确保产物已重建，再验证 HMR 或页面刷新后实际加载的新代码

## 参考实现

- `dsh-loop`（`/loop` 命令 + loop 工具 + client 状态条）
- `dsh-task-status`（后台任务状态条）
- 薄控制台 `packages/plugin/console`（本仓库，bundle 形态的官方样例）
