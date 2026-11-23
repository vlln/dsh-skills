# 安装与验证详情

> **本文件回答**：安装通道、按改动面验证、**本地开发实例**（独立进程 / 持久私有 home / 固定端口 / 用户手动验收）、负控、图标验收、排查顺序。**不回答**：发布与推广（→ 11 / 12）、纪律清单（→ 09）。

**来源**：本 skill 的**验证纪律**（负控、按改动面取最窄证据）＋ 对官方 `apps/cli/reference/README.md`
（安装 / 层栈行为）与 `dsh-hmr` / `dsh-plugin-manager` / `cordis-plugin-loader` 的实测核查；
"哪个版本会怎样"是实测记录，不是跨版本承诺。复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

外部插件统一经 web profile 安装，两条通道：

## Bundle 插件安装

```sh
dsh plugin --profile web add <包路径>
```

`<包路径>` = 含 `package.json#dsh.bundle` 的 npm 包目录/git 源（`dsh plugin add` 转发 pnpm + 按已安装状态把声明 `dsh.bundle` 的依赖加进 profile 层栈）。本地目录 `cd` 到包目录后 `add .`（dsh 锚定 `.` 为绝对路径）；git 源 monorepo 子目录 `#<commit>&path:/<子目录>`（**Windows 注意：`dsh plugin` 经 cmd.exe 转发，`&` 是命令分隔符会拆开命令——给用户的安装说明写不带 `&` 的 `#path:/<子目录>` 形式，取默认分支 HEAD，跨平台；钉分支需绕开 dsh 转发，见 [13-gotchas.md](13-gotchas.md) 1c**），**产物入库（推荐）→ 真一行**，不入库则 `prepare` + `allowBuilds` 放行——写法细则与坑见 [05-bundle-plugins.md](05-bundle-plugins.md)「安装与管理」与 [13-gotchas.md](13-gotchas.md) 1c；bundle 不声明官方包依赖（见 [13-gotchas.md](13-gotchas.md) 1）。安装后检查实际挂载状态；是否需要重启见下表，不由 bundle 形态单独决定。

## Desktop 安装

官方 Desktop 上从**应用内的 Plugins 页**安装（共享插件管理器 + 内置 pnpm）；`$DSH_HOME/profiles/desktop` 由 Electron 独占，npm 安装的 `dsh` 不能改它，CLI 也不能启动该 profile。Desktop 自带的 `dsh` 命令可在**完全退出应用后**管理它。版本、调试与恢复见 [14-desktop.md](14-desktop.md)。

## 纯 cordis 插件安装

```sh
dsh plugin --profile web add <包>       # 装依赖（进 profile node_modules）
```

然后 profile `cordis.patch.yml` 写 insert 行（启用配置热协调时可实时挂载；CLI add 普通依赖本身不自动生成 insert）：

```yaml
- insert:
    - id: my-plugin
      name: 'my-plugin'                 # 必须加引号（YAML @ 开头是保留指示符）
```

## 验证按改动面

**核查记录：0.2.0-rc.2 实测 + 0.2.1-rc.1 复核（HMR 替换语义）；不是对所有版本的承诺。**
先查有效组合中是否有 `hmr` 服务，以及源码 watcher 的 root/ignored。`dsh-base` 在有 `profileContext`
时以 **`root: []`** 启用 HMR（仅配置热协调）；`dsh-hmr` 自身的默认是 `root: ["."]`、`ignored`
含 `**/node_modules` / `**/.*` / `cache` / `data`——**源码监听要显式开**。

| 改动 | 该版的处理与验证 |
|---|---|
| CLI 新增/移除 bundle | 安装器更新 profile bundles 列表；有 HMR 时监视 manifest 并重新协调层栈。验证插件实际挂载/卸载，不默认重启 |
| GUI 首装 bundle、启停 | 有 HMR 时调用配置协调；没有 HMR 时按返回的 restart-required / stop-profile 提示处理 |
| 已装包升级、同路径重装 | 0.2.1：**下一次 profile 重组**会替换磁盘上已变化的插件，**包括 `node_modules` 下的已安装包与 link 目标**，不需要 root 监听；重组由 bundles 列表、profile/home patch、plugin manager 操作触发。文件变了但没触发重组时看不出变化——主动触发再验证，别把"重装"当热更新 |
| volatile 配置 | 仅 volatile 值变更时原地更新；其他配置变更可能重新挂载 |
| Node half 源码 | 两条路径：① 源码 HMR（显式配置 `root` 且路径命中、不被 `ignored` 排除）② profile 重组时的文件变化替换（覆盖 `node_modules`/link，无需 root）。替换加载失败 → 插件以 `failed` 报告（不是"需要重启"）。都不生效才重启兜底 |
| client half | 先重建产物；按客户端 HMR / 页面刷新验证新 bundle。HMR 接收器存在不等于构建 watcher 在运行 |
| 样式 / 布局（client CSS） | 真机里读 `getComputedStyle` 确认规则**命中**——页面里存在我们的 `<style>` 不算证据（未闭合的 `@media` 块会把后续规则整段吞掉：语法合法、构建通过、单测全绿，见 [13-gotchas.md](13-gotchas.md) 20） |
| 顶层 icon / 图标资源 | 元数据读取直接读 manifest 与图片文件；刷新 Plugins 数据可更新，无须据此重启 Node 插件。仍需验证实际图片和打包结果 |
| bundle 内部 patch 单独变化 | 不等于 profile bundles 列表变化；须验证配置重读是否实际触发，不假定所有文件都受 watch |

依据：`dsh-hmr/lib/index.js` 的 profile manifest watcher、partialReload；
`dsh-plugin-manager/lib/index.js` 的 installPackage/reload/listBundles；
`cordis-plugin-loader/lib/index.js` 的 volatile 更新；`dsh-app-boot` 的 readPluginMeta/iconOf。
升级基线时重新核查这些路径，**不要再以“ESM 有缓存”推出“一律重启”**。

图标补充实测：autofork 仅新增 manifest icon 与 SVG 后，刷新隔离实例的 Plugins 页即显示新图标，
`decode()` 成功；该操作未重启服务。此证据仅覆盖元数据/图标，不证明 Node 代码热更新。

## 插件图标：机械验证与视觉验收

绘制/修改图标及发布插件时执行。先核对**实际安装运行时**的
`@deepseek-ai/dsh-package-manifest` 类型与 `dsh-app-boot` 的 `iconOf`、manifest
读取逻辑，并记录版本；不要用领先的 master 文档替代安装版契约。

**运行时契约**：`package.json` 顶层 `icon?: string`（不是 `dsh.icon`）。
路径相对 manifest 目录，支持 SVG / PNG / JPEG / WebP，文件大小 **≤256 KiB**；
解析后的 **realpath 必须仍在 manifest 目录内**，符号链接不能绕过目录边界。
`iconOf` 按扩展名、路径、大小校验后转成 data URL；宿主读取包导出的
`package.json`。它不是 client bundle 内的图标组件，也不经普通 assets 路由。

### 机械验证（可自动断言，不证明好看）

- 检查顶层 `icon` 路径、扩展名、字节数及 realpath 边界；SVG 能解析且自包含，
  无字体字形、外链、脚本，不依赖宿主 `currentColor`。
- 检查 `files` 白名单包含图标，`exports["./package.json"]` 指向 manifest；
  **检查实际 pack 的 tarball 内容**，不能只看工作树。安装该产物后从 profile
  解析 `<包名>/package.json`，确认读到的 `icon` 及图标文件都正确。
- 用隔离 `DSH_HOME` 和独立端口安装、启动验证宿主，刷新并打开**侧边栏 Plugins 页**。
  定位该包的实际 `<img>`，确认 `src` 是预期图标的 data URL，而非默认占位图；
  等待加载后断言 `complete === true` 且 `naturalWidth > 0`（可再用 `decode()`）。
  文件存在、页面 200、DOM 中有 `<img>` 均不足以证明图片成功加载。

### 视觉验收（必须实际看渲染结果）

- 查看真实 Plugins 页截图/浏览器中的图像，在列表实际尺寸及浅/深主题下检查：
  轮廓可辨、留白与官方图标协调、没有裁切或过细笔画，颜色对比足够、透明背景正常。
  放大预览可辅助，但不能代替实际展示尺寸。
- 对用户指定标记核对形状与语义，不以字体渲染是否恰好成功代替路径绘制。
- **分别报告机械检查与视觉检验的证据**（运行时版本、产物、页面/截图与观察结论）。
  没有浏览器或无法查看图片时，明确写“视觉验收未完成”，请用户看图确认，
  不得把解析成功、尺寸断言或文件存在写成“视觉通过”。

## 验证的三条硬规矩

1. **boot 干净 ≠ 功能可用**。依赖解析失败与服务名写错在 boot 期**看不见**（服务惰性读取，错误只在调用时抛）——插件照样装载、工具照样注册。因此「URL 正常输出 + 日志无 `plugin tree failed to load`」是必要不充分，**必须经真实入口调用核心功能**看结果（工具/命令或 UI 闭环）。
2. **先做负控（prove the failure mode is loud）**。把一份**故意弄坏**的副本装上（删掉 `inject`、或把包放到 profile 树外），确认日志会响亮报错；只有负控响过，"干净日志"才算证据。
3. **mock ctx 单测不能替代真实装载**。手写 mock 不施加 cordis 的严格注入门禁，所以"`apply()` 里注册了 N 个工具"的测试**照不出**缺 `inject` 的启动即崩。单测证明"逻辑对"，真实 profile 启动证明"装得上、起得来"——两者都要，不能互相代替。

验证环境用**安装版 dsh**（`npm i @deepseek-ai/dsh@<rc>`）与隔离 `DSH_HOME`——直接跑源码 checkout 会因官方包镜像不完整而整树失败，见 [13-gotchas.md](13-gotchas.md) 9。

## 两类隔离环境（先按用途选）

| 用途 | home / 端口 | 保留与清理 |
|---|---|---|
| 自动回归 / 干净安装 | 每次新建临时 home、独立 workspace、随机端口 | 不读真实凭据；收集结果后在 finally 等待浏览器与进程退出，再核对绝对路径清理自建目录 |
| 用户手动验收 / 连续开发 | 项目约定的持久私有 home、每插件一个稳定端口 | 重启不删会话，不偷偷换端口；用户确认结束后才清理 |

两类都不复用主 GUI、真实 `DSH_HOME` 或用户工作区。**只换 home 不一定隔离工作区**，需显式给宿主 workspace 配置测试目录。
路径服从项目规则；无约定时用项目 `.work/<插件>/`，不擅自在 home 根创建目录。自动测试默认不复制凭据；需真模型/账号时先确认授权，仅复制所需项、不读取或输出凭据本体。
若项目约定一次性验证站，遵守该约定；需要保留用户会话时先确认再改生命周期。不可用的依赖应在必跑 CI 中失败，不用 skip 假装已验证。门禁选择见 [16](16-engineering-patterns.md)。

## 本地开发实例（人工验收，连续开发）

**用户手动测试才是验收**：开发过程中每做完一块，以及功能完成后增加 / 修改功能，都起一个**独立实例**，
把 URL 与测试点交给用户亲手点一遍。agent 自己"跑通了"只是必要不充分——**URL 能打开 ≠ 插件在**：
插件解析失败时宿主照常起来、界面看起来完全正常，只有日志里两行字（见下面实测症状）。

**三件事**：独立进程、**项目约定的持久私有 `DSH_HOME`**、**每个插件一个稳定端口**。

| 不变量 | 做法 | 违反时的现场表现 |
|---|---|---|
| 进程独立 | 自己的 dsh 进程，不共用主 GUI | 半成品留在用户 profile 里 |
| home 持久且私有 | 从项目规则取路径，建一次、复用；结构性拒绝与主 home 的 realpath 相同，也不盲读继承来的 `DSH_HOME` | 每次回来会话没了（用户以为插件吃了历史）；两个写者损坏同一份会话日志 |
| 端口固定 | 只挑一次（排除 3080），存进 home 的 `web-port`，以后每次都用；被占用时报错并给 `lsof -nP -iTCP:<port> -sTCP:LISTEN`，**不许悄悄换** | 旧 URL 全部失效，用户以为进程挂了 |
| 凭据 | 默认无真实凭据；确需真模型时经授权复制所需配置、收紧权限、不输出内容，之后不覆盖 | — |
| 启动环境 | **不要从受限沙盒里的 shell 启动**：seatbelt 不能嵌套，实例会误判 workspace-write 不可用，退化成"每条命令都要授权"。确实只有沙箱内的 shell 时，**申请沙箱外权限去启动**（一次性 danger-full-access），不要为了绕开权限另建 home / 换端口 | agent 频繁申请权限，被误读成沙盒坏了；或悄悄多出一套测试环境，会话与端口都对不上 |

实现仓库自己的 `dev:host`（参考 [16](16-engineering-patterns.md) 的能力，不跨仓库调用脚本），按序做：

1. 从项目约定解析 home；建目录后用 realpath 拒绝共享主 home。记录拥有的进程与目录，不替用户结束现有服务。
2. 安装正在开发的包。link 先验证 SDK 解析；tarball 要明确本次版本/哈希，避免同版本缓存拿到旧产物。
3. 首次请求空闲端口并排除主 GUI；写入 home 的端口文件。再次启动读取同一端口；校验合法数值、排除主端口，被占用即报错，不自动改号。
4. 用受管后台进程启动宿主（不脱管 nohup）；等待就绪且观察早退/超时，失败时清理自己创建的子进程。
5. 从本进程日志取当次 URL，仅在验收交接时提供；自动测试验证 origin/redirect 并以 cookie 访问干净 URL，不把 token 写入测试报告。

URL 里的 `token` **每次启动重新生成**（web 应用只有 `--host` / `--port` / `--public-url` / `--tls-*`），
所以端口稳定 ≠ URL 不变：每次从日志取当次 URL 交给用户，不要承诺固定地址。默认会打开本机浏览器；
远程 / 无人值守加 `--no-open`。

**本地目录（link）的前置条件**：树外 link 若未采用已验证的开发 SDK，可将匹配运行时的 SDK 链接到插件自己的 `node_modules`（[13](13-gotchas.md) §1、§6）。下面仅示意空目录配方；已有目录/链接时先检查目标，不能用强制链接覆盖真实依赖：

```sh
DSH_PKG="$(dirname "$(dirname "$(readlink -f "$(command -v dsh)")")")"   # …/@deepseek-ai/dsh
mkdir -p node_modules
ln -sfn "$DSH_PKG/node_modules/@deepseek-ai" node_modules/@deepseek-ai
ln -sfn "$DSH_PKG/node_modules/@deepseek-ai/cordis" node_modules/cordis
```

漏了这一步的实测症状（0.2.1-rc.1）：**实例照常起来、URL 照常能开**，插件功能与 UI 一起消失，
日志里只有 `failed to import ... Cannot find package 'cordis'` + `warning: 1 entry did not activate`。
`node_modules/@deepseek-ai` 已是真实目录时，按第 1 条逐个包 link。纯 cordis 形态还要在**这个隔离 home**
的 profile `cordis.patch.yml` 里写 insert 行（见「纯 cordis 插件安装」）。

**需真实数据复现时**：用户明确授权后，将最小必要副本放入私有测试环境；不要自动复制整个真实 home。用户要在自己的环境里看时，让用户自己安装 / 启动。

**每轮改动的循环**：改源码 →（有构建才）重建产物 → 按「验证按改动面」确认热更新或重启这个 dev 实例 → 刷新页面 → 真功能回归 → 把本轮 URL 与测试点交给用户。
同一时刻只给用户**一个**地址；**用户正在测的时候不要重启 / 换实例**（会打断他、丢失会话状态）。

**交接前自检**（否则用户看到的是一个"正常但没有插件"的界面）：

- 启动日志无 `failed to import` / `did not activate`；Plugins 页能看到本插件；
- 挂的是**本次目标版本**：link 核对 realpath 指向开发目录；tarball / npm / git 核对安装版本、来源与构建指纹或哈希，不把旧缓存当新产物；
- 真调过一次工具 / 命令或 UI 功能闭环（不是只看了首页）；
- **端口和上次一样**（变了就是没固定住，用户手上那个地址已经失效）；
- 消息里给全：URL（含 token）、**这是隔离实例**（空会话、不碰真实数据）、要测的 3–5 个点、怎么停。

**端口与进程纪律**：固定端口见上；不要结束用户正在用的 dsh Web GUI（默认 `3080`），也不要泛模式 `pkill`；替换实例前
按端口确认进程归属（`lsof -nP -iTCP:<port> -sTCP:LISTEN`）再结束旧的。任务结束后实例与 `<home>`
可以留到用户确认为止，确认完再清理。

## 随包分发 skill（走文件系统发现根）

skill 是跨 harness 的规范，落位方式是**复制或链接 `skills/<name>/` 进发现根**：项目级 `<项目>/.dsh/skills`、`<项目>/.agents/skills`；用户级 `$DSH_HOME/skills`、`~/.agents/skills`（另有 custom 与 bundled 两类）。`dsh.skills` 声明在当前基线不生效——事实与核实方法见 [04-plugin-contract.md](04-plugin-contract.md)「dsh.skills」。

安装说明要给**可直接复制**的命令，例如（插件已装好的用户级链接）：

```sh
ln -s "$DSH_HOME/profiles/web/node_modules/<pkg>/skills/<name>" "$DSH_HOME/skills/<name>"
```


## 挂载失败排查

`plugin tree failed to load` 的排查顺序与严格注入/引号坑见 [13-gotchas.md](13-gotchas.md) 3。

## 参考实现

- 仓库内参考实现：`packages/plugin/console`（bundle + `__ModuleLoader__.load` client 完整例子）
