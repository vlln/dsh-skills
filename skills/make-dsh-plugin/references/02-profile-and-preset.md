# Profile 与 agent preset：装配机制

> **本文件回答**：profile 目录与层栈、preset 声明与选择、分发与覆盖、Host-vs-preset。**不回答**：从零搭产品的顺序（→ 03）、entry / manifest 字段（→ 04）。

**定位**：概念与两棵树的由来见 [01-concepts.md](01-concepts.md)；本篇是**可照做的机制细节**（目录、模板、层栈、生命周期、分发与覆盖）。只想搭一个垂直 Agent 的话，先看 [03-vertical-agent-recipe.md](03-vertical-agent-recipe.md)。

**来源**：官方 `apps/cli/reference/README.md`（Profile 启动 / 插件管理 / 层栈）、`packages/boot/app-boot/README.md`（profile 初始化、模板、层、兼容性）、`packages/util/package-manifest/src/types.ts`（`dsh.bundle.patch: string | string[]`）、`packages/preset/{agent-preset,agent-preset-registry,persona}/README.md`、`packages/client/ui-agent-preset/README.md`、`docs/subsystems/permission-presets.md`；**随包 skill** `@deepseek-ai/dsh-agent-preset/skills/editing-cordis-compositions`（写 preset 的官方口径）；实测：安装版 **0.2.1-rc.1**（隔离 `DSH_HOME` 跑 `--dump-default-config` 看真实初始化文件与层标签；另按 §2.5 的最小 preset bundle 走通 `add` → bundles 列表 → `--dump-config` 出现 `preset-review` 行）与 master **0.2.1-rc.2**（源码路径）。复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

**一句话**：**profile 决定一个进程装了什么**（宿主插件树 + 安装/解析边界）；**agent preset 决定每个 Agent 在自己的隔离子树里看得见什么**（工具 / 提示词 / 技能）。两者都是 Cordis 补丁层，差别在挂载点与生命周期：profile 一次启动一棵树；preset 是树里的 `preset-<id>` 行，被会话选中后分出一棵独立子树。

## 0. 先分清三个「preset」

| 名字 | 是什么 | 作用面 | 谁在用 |
|---|---|---|---|
| **profile** | `$DSH_HOME/profiles/<name>/` 一套装配 + 依赖 | 整个进程 | 启动器 `dsh --profile <name>` |
| **agent preset**（本页简称 preset） | 一行 `@deepseek-ai/dsh-agent-preset` 声明 = 一个 Agent 的子插件列表 | 单个 Agent / 会话 | registry 按会话选 |
| **permission preset** | 沙箱模式 + 审批策略的具名组合（`workspace-write`、`danger-full-access`） | 会话执行策略 | `permission-presets` 服务 |

⚠️ 三者互不替代。permission preset 只是把 `sandbox/mode` 与 `approval/policy` 绑成命名选项（见 `docs/subsystems/permission-presets.md`），跟工具组合无关；基于 base 的 profile 里新会话默认 `workspace-write`（由宿主策略与 `DSH_PERMISSION_MODE` 决定），那是 permission preset 的事。

## 1. profile

### 1.1 目录里有什么

| 文件 | 作用 | 谁写 |
|---|---|---|
| `package.json` | `name: dsh-profile-<name>`、`private`、`dependencies`、**`dsh.profile.bundles` 有序列表** | dsh 初始化、pnpm / 插件管理器 |
| `cordis.patch.yml` | 用户层（模板起步是 `[]` + 注释），GUI 设置也落这里 | 用户 / 设置页 |
| `pnpm-workspace.yaml` | `packages: ['.']`、`nodeLinker: hoisted`、`autoInstallPeers: false`（`allowBuilds` 在需要放行构建时追加） | dsh 初始化 / 用户按提示追加 |
| `cordis.yml` | Loader 根，恒为 `[]`；**每次启动重写**（防止组合行被写回而重复挂载） | launcher（别手改） |
| `node_modules` / `pnpm-lock.yaml` | 装进 profile 的 bundle 与依赖 | pnpm |
| `$DSH_HOME/cordis.patch.yml`（home 级） | 跨 profile 共享的机器本地偏好 | 用户 |

实测（0.2.1-rc.1，隔离 `DSH_HOME` 跑 `dsh --profile web --dump-default-config`）：首次会留下 4 个文件——`package.json`（`dependencies: {}`、`bundles: ["@deepseek-ai/dsh-base","@deepseek-ai/dsh-web-app"]`）、`cordis.patch.yml`（`[]`）、`pnpm-workspace.yaml`（以上由 init 写），外加 launcher 在每次准备 profile 时无条件重写的 `cordis.yml`（`[]`）；不装 node_modules——随附包直接从 dsh 安装目录解析。

### 1.2 随附模板与创建

| profile | bundles | 首次使用 | patch 应用时机 |
|---|---|---|---|
| `web` | base + web-app | 自动初始化 | 实时（HMR） |
| `headless` | base + headless | 自动初始化 | 只在启动时 |
| `sdk` | base + sdk-app | 自动初始化 | 只在启动时 |
| `sdk-minimal` | sdk-minimal（独立，不含 base） | 自动初始化 | 只在启动时 |
| `acp` | base + acp-app | 自动初始化 | 只在启动时 |

- `dsh <name>` 是 `dsh --profile <name>` 的简写；`plugin` 例外——`dsh plugin …` 是管理命令，启动同名 profile 要写 `dsh --profile plugin`。
- **自定义 profile**：`dsh plugin --profile <name> add <pkg>` 首次会初始化（只含 `@deepseek-ai/dsh-base`）；`dsh --profile <name>` 对未初始化且非模板的名字**显式报错**并提示这条命令。
- **模板复制**：`dsh --profile <name> --from-default-profile <web|headless|sdk|sdk-minimal|acp>` 用模板的**全新副本**替换自定义目标——**丢弃**其依赖与原 patch；目标名不能是随附名（大小写不敏感），`desktop` 保留给 Electron 应用（见 [14-desktop.md](14-desktop.md)）。替换失败回退，回退也失败时旧目录留在 `profiles/.<name>.staging-*/previous`。它只复制 **bundle 列表**，不读同名随附 profile 的本地状态。
- profile 名规则：非空、不含 `/ \`、不是 `.` / `..` / `node_modules`；其余不限（小写连字符的限制只针对 preset id）。

### 1.3 层叠顺序（唯一的装配规则）

| # | 层 | 位置 | 属主 |
|---|---|---|---|
| 1 | 各 bundle 的 patch | 按 `dsh.profile.bundles` 顺序；每个 bundle 内再按 `dsh.bundle.patch` 的文件顺序（**可为数组**） | 产品开发者 |
| 2 | profile 层 | `$DSH_HOME/profiles/<name>/cordis.patch.yml` | 用户（含 GUI 设置） |
| 3 | home 层 | `$DSH_HOME/cordis.patch.yml` | 用户（跨 profile，优先级高于 2） |
| 4 | `--patch <path>` overlay | 按 argv 顺序（相对路径按 CWD 解析） | 一次性实验 |

语义三条：**按行 id 命中，替换该行的整个 `config`（不是深合并）**；patch 也能 `insert` 新行；命不中目标时 stderr 警告。完整的 patch 方言与可装包清单见创造模式的 `cordis-composition-reference`（只在该 preset 挂载）。**空 patch 文件会导致启动失败**——要禁用该层写 `[]`。层标签用 dump 看最直观：

```sh
dsh --profile web --dump-default-config   # 只看 bundle 层
dsh --profile web --dump-config           # + profile patch + home patch + --patch
dsh --profile web --dump-config-schema    # 插件 Config 的 JSON Schema（会 import 插件）
```

`--dump-config` 用注释标出每行来源（`# == @deepseek-ai/dsh-base, patched by @deepseek-ai/dsh-web-app`）。

### 1.4 bundle 列表语义

- **装**：`dsh plugin --profile web add <spec>` → pnpm 装进 profile；若该依赖声明了 `dsh.bundle.patch`，自动加入 `dsh.profile.bundles`。不声明组合层的普通依赖照常保留 + 一次性警告。
- **卸**：退出列表 + `pnpm remove`。
- **启停**：只改 profile patch 里的 `disabled`；**bundle 开关改 bundles 列表**。关闭保留依赖；**开启追加到列表末尾 ⇒ 可能改变层优先级**（后应用的 bundle 覆盖前面的行）。
- `OPTIONAL_BUNDLES`：随安装提供、默认关闭、永不卸载、任何随附模板都不选中的 experimental bundle（插件页可开）。
- **重启边界**：bundles 列表变化要重启 profile 才生效（装 / 卸 / 升级 bundle）；profile 与 home patch 的普通编辑在有 HMR 时热应用。**重装同版本 ≠ 代码热更新**。

### 1.5 解析与安装位置（为什么必须装进 profile）

- bundle 解析顺序：**先 dsh 安装目录，再 profile 目录**；随附 bundle 始终来自当前运行的那个 dsh。
- 挂载前 launcher 算一份**不可变 runtime resolution** 装进 Node 的 ESM/CJS resolver（不建 fallback 链接）：安装优先 + 按 bundles 顺序做依赖图 BFS。
- profile 的 node_modules 由 pnpm 管理；`nodeLinker: hoisted` 让树外插件拿到扁平 node_modules，缺的 peer 走 runtime resolution ⇒ 全 profile 共用一个 cordis 实例（这正是官方 `pnpm-workspace.yaml` 模板存在的原因）。
- 实践结论：**装进 profile 树内才有官方包可解析**；从树外目录装（本地 `add /abs/path`）会让**整棵 profile 起不来**（现象与本地自测配方见 [13-gotchas.md](13-gotchas.md) 6）。

### 1.6 兼容性与跳过

- 宿主校验 `engines.dsh`（声明了它就只认它），否则校验 `peerDependencies` 里的 `@deepseek-ai/dsh` / `@deepseek-ai/dsh-*`；不满足 ⇒ 该 **bundle 被跳过**（记入 `skippedBundles`，启动时报告一次），其余照常启动。
- 精确版本豁免写 profile 的 `compatibility.json`（不碰 `package.json` / patch；升级不继承授权）。
- 单个插件行被拒 ≠ 整树失败：普通行变游离的 `disabled: true`，native group 保留而子行不加载；**profile / home patch 自身写错仍导致启动失败**。

## 2. agent preset

### 2.1 是什么

两层结构：

1. **声明行**：`@deepseek-ai/dsh-agent-preset` 的 `config.plugins` 就是该模式挂的子插件列表（普通 Cordis entry list，可含 `cordis:group`、`!!js`）。声明**提前激活**，修改只影响之后创建的 Agent。
2. **注册表**：`@deepseek-ai/dsh-agent-preset-registry`（`ctx.agentPresets`）负责选择与代际保留；它给每个声明建独立 scope + 内存 Loader 树，Agent 的 scope 链接到所选代际，**子 Agent 继承父方的确切代际**。默认项由设置面写回 profile 层（不是注册表自己改文件）。

所以同一进程可以同时跑能力不同的 Agent，共享宿主服务与 Agent loop；工具、提示词、技能按 Agent 隔离。

### 2.2 随附四个（来自 `@deepseek-ai/dsh-web-app` 的 `presets/*.patch.yml`）

| id | order | GUI 文案 | 组合要点 |
|---|---|---|---|
| `standard` | 1 | 标准模式 | 完整工具集（shell / fs / jobs / schedule / subagent / workflow / plan / todo / web / present / skill…） |
| `ptc` | 2 | PTC 模式 | standard 的工具集 + `agent-tool-presentation`（`mode: ptc`：模型只见 `run_code`，不逐个暴露工具 schema），并**关掉 `workflow-ptc` / `tool-workflow`** |
| `minimal` | 3 | 极简模式 | `persona`（`complete: true`、`includeRuntimeContext: false`）+ fs 只留 `read_image` + 持久 shell + 压缩 |
| `cordis` | 4 | 创造模式 | standard + `plugin_manager` / `plugin_market` 工具 + 造 bundle 的 skills（`cordis-plugin-development` 等） |

- GUI 里叫「**模式**」（新任务选择器 / 设置页卡片）；该页的标题是「**Agent 预设界面**」（`ui-agent-preset` 的 `meta.title`），文档正文用「agent preset」。
- 设置页关闭「代码工作工具」后，选择器与列表只留 `standard` / `cordis` / 自定义；重新开启才恢复 PTC 与极简。关闭被接受后，已保存的 PTC / 极简默认值回退为 `standard`（已有会话保留其模式，选择只影响之后的任务）。
- 内置 id 的文案走 locale 字典：声明**不给 `name`** 且 id 命中内置四个才被当作内置；自定义 preset 请自己给 `name`（不给时卡片标题回退为 `id`）。

### 2.3 声明格式

```yaml
- insert:
    - id: preset-review              # Loader 编辑地址，约定 preset-<id>
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: review                   # 会话记录的稳定身份（小写字母 / 数字 / 连字符）
        name: Review                 # 展示名（自定义必给）
        description: Reviews changes with the shell only.
        order: 10                    # 列表排序
        plugins:                     # 必填：子插件 entry list
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config:
              prefix: You review software changes.
          - id: tool-bash
            name: '@deepseek-ai/dsh-tool-bash'
```

- **行 `id`** 是 Loader 的编辑地址；**`config.id`** 是会话日志里记录的身份——**改 `config.id` 等于换身份**，老会话恢复时找不到定义会被拒绝。
- **覆盖内置 preset**：按行 id 写覆盖，`config` 整块替换（**不是合并**），必须重述 `id` / `plugins` 及原文件的 `order` 等字段；覆盖后该 preset 不再跟随上游更新：

```yaml
- id: preset-standard
  name: '@deepseek-ai/dsh-agent-preset'
  config:
    id: standard
    order: 1
    plugins:
      # 这里必须是完整列表（从官方文件整份复制后再改），不能只写注释
```

### 2.4 选择与生命周期

| 时机 | 行为 |
|---|---|
| 部署默认 | registry 的 `config.default`（必填） |
| 用户默认 | `agent-preset-registry` 行的 volatile `selectedDefault`，新会话优先于 `default`；GUI 选择默认项就写它（最终落在 **profile patch**） |
| 新会话 / 空白会话切换 | 记录 `agent-preset/selected` 事件；空白会话可 `select` 换（同 preset 为 no-op）；**首个 turn 一开始就锁死**，再选会得到 `agent-preset/locked` 错误（RemoteError，不是事件） |
| 恢复会话 | 按记录的 id 解析**当前**定义；定义缺失 ⇒ 拒绝恢复 |
| 子 Agent | 继承父方的确切代际（不是默认 preset） |
| 定义被更新 | 旧代际退役，仍被引用的 Agent 保留到最后一个引用释放 |
| 定义激活失败 | 仍留在列表并带诊断；拒绝新绑定，但**不阻止应用启动**（可在 Web 里修） |

### 2.5 新建 / 覆盖 / 分发

官方口径（随包 skill `editing-cordis-compositions`）：**preset 只能由「装一个 bundle」创建或修改**，没有原地编辑；GUI 的 preset 页只读（「查看配置」），创建/修改走**创造模式**（`cordis` preset 里让 Agent 写 bundle，再 `plugin_manager install_bundle`；流程与边界见 [05-bundle-plugins.md](05-bundle-plugins.md)「创造模式」）或直接写 patch。

最小两文件 bundle：

```jsonc
// review-preset/package.json
{
  "name": "@local/dsh-review-preset",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }
}
```

```yaml
# review-preset/cordis.patch.yml
- insert:
    - id: preset-review
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: review
        name: Review
        order: 10
        plugins:
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config: { prefix: You review software changes. }
          - id: tool-bash
            name: '@deepseek-ai/dsh-tool-bash'
```

安装：`dsh plugin --profile web add <包>`（或 GUI / 创造模式里的 `plugin_manager install_bundle`；本地目录自测的前置条件见 [13-gotchas.md](13-gotchas.md) 6）。**bundle 的 `patch` 可以是数组**——官方 web-app 就是 `["cordis.patch.yml", "presets/standard.patch.yml", …]` 按序拼接，所以一个包能同时分发宿主行与多个 preset（见 [05-bundle-plugins.md](05-bundle-plugins.md)）。

- 子行按普通行解析（安装目录 / profile 树），引用的插件必须可解析：官方包随安装提供，自写插件随同一 bundle 进 profile。
- **只声明 preset 的 bundle**（patch 里不 insert 指向自身的行）不会被 import——实测本地目录装也进得了列表、dump 里行与子行齐全；一旦 preset 子行引用你自己的插件包，就回到 gotcha 6 的解析约束。
- 旧形态 `$DSH_HOME/.agent-presets/<id>/`（`preset.yml` + `agent.cordis.yml`）**已退役**，迁移 = 原样搬进声明行（插件名要按当前版本核对）。

### 2.6 Host 还是 preset：放置判据

| 放 Host（profile 层） | 放 preset |
|---|---|
| 服务、Agent loop、session / 持久化、settings、sandbox / 审批、模型路由、subagent 后端、**工具注册表本身** | 带作用域的工具、persona、prompt 段、策略、技能 |

- 判据是**消费者在哪**：服务只有在其全部消费者一起下沉时才能下沉。`agent-tool-presentation` 的官方论证值得记住——工具注册表搬不进 preset（消费者都在宿主平面），**preset 能拥有的是「呈现方式」**，所以 PTC 与 native 能在同一进程并存。
- preset 里的服务提供方与消费者必须共享同一个隔离 realm（`cordis:group` + `isolate`）；组外的普通 Context 查找（包括 `agent.ctx`）仍走 Host realm。
- `!!js` 只写在插件 `config` / `disabled` 上（由 Loader 在激活子插件时求值）；资产从**安装包**解析，不要指望 preset 目录。

### 2.7 验证

- `list_bundles` 看 bundle 是否进了列表；`list_plugins` 看 `preset-<id>` 行的激活状态（坏定义也在，带诊断）。
- 从 dump 里确认行与子行都进了树：`dsh --profile web --dump-config | grep -A6 'id: preset-review'`。
- **改了 preset 必须新开会话**验证：已有会话与子 Agent 保留启动时的代际。
- 自定义模式的卡片出现在设置页 = 声明被 registry 接受；点「查看配置」能读回 YAML。

## 3. 交界：要加的东西放哪层

| 能力 | 层 | 分发 | 用户可见点 |
|---|---|---|---|
| 工具（所有 Agent 可用） | Host 行（bundle patch `insert`） | bundle | 新会话即可用 |
| 工具（只在某个模式） | 该 preset 的 `plugins`（或覆盖内置 preset） | bundle | 对应模式的新会话 |
| 命令 / 服务 / 设置页 / Web UI | Host 行 | bundle | 重启或配置热协调后 GUI 可见 |
| 新的「模式」 | preset 声明行 | bundle | 设置页卡 + 新任务选择器 |
| 宿主提供方 + Agent 工具（如 subagent 后端） | **两处**：Host 行注册服务，preset 行挂 `tool-*` | bundle | 该模式的新会话 |

## 4. 边角（易混）

- `--from-default-profile` 只复制 **bundle 列表**，不继承同名随附 profile 的依赖 / patch，也不会后续跟随模板变化。
- 同一个 preset 行，**在 bundle 里覆盖 = 产品级定制**（随包分发）；**在 profile patch 里覆盖 = 用户级定制**（不进包，只影响本机）。
- preset 不提供安全沙箱：`sandbox` / `approval` 由 permission preset 与宿主策略决定。
- **extensions 子系统 ≠ preset**：前者让 Agent 写版本化的 Cordis 包并运行其 host/client 两半（`docs/subsystems/extensions.md`），与这里的选择机制无关。
