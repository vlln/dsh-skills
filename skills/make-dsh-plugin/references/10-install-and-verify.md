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

1. **boot 干净 ≠ 功能可用**。依赖解析失败与服务名写错在 boot 期**看不见**（服务惰性读取，错误只在调用时抛）——插件照样装载、工具照样注册。因此「URL 正常输出 + 日志无 `plugin tree failed to load`」是必要不充分，**必须真调一次工具/命令**看返回。
2. **先做负控（prove the failure mode is loud）**。把一份**故意弄坏**的副本装上（删掉 `inject`、或把包放到 profile 树外），确认日志会响亮报错；只有负控响过，"干净日志"才算证据。
3. **mock ctx 单测不能替代真实装载**。手写 mock 不施加 cordis 的严格注入门禁，所以"`apply()` 里注册了 N 个工具"的测试**照不出**缺 `inject` 的启动即崩。单测证明"逻辑对"，真实 profile 启动证明"装得上、起得来"——两者都要，不能互相代替。

验证环境用**安装版 dsh**（`npm i @deepseek-ai/dsh@<rc>`）与隔离 `DSH_HOME`——直接跑源码 checkout 会因官方包镜像不完整而整树失败，见 [13-gotchas.md](13-gotchas.md) 9。

## 本地开发实例（开发中与每次改动后的标准动作）

**用户手动测试才是验收**：开发过程中每做完一块，以及功能完成后增加 / 修改功能，都起一个**独立实例**，
把 URL 与测试点交给用户亲手点一遍。agent 自己"跑通了"只是必要不充分——**URL 能打开 ≠ 插件在**：
插件解析失败时宿主照常起来、界面看起来完全正常，只有日志里两行字（见下面实测症状）。

**三件事**：独立进程、**持久的私有 `DSH_HOME`**、**每个插件一个固定端口**。

```sh
# 1) 私有 home：建一次，之后每次复用；不要每次新建，也绝不指向 ~/.dsh
export DSH_HOME="$HOME/.dsh-<任务名>"
mkdir -p "$DSH_HOME"

# 2) 把正在开发的包装进去：本地目录走 link，改源码不用重装
dsh plugin --profile web add /abs/path/to/my-plugin

# 3) 端口：第一次挑一个空闲的（避开 3080），写进 home，此后永远复用它
PORT_FILE="$DSH_HOME/web-port"
[ -f "$PORT_FILE" ] || node -e 'const n=require("net");const s=n.createServer();s.listen(0,"127.0.0.1",()=>{const p=s.address().port;s.close(()=>console.log(p))})' > "$PORT_FILE"
PORT="$(cat "$PORT_FILE")"

# 4) 起实例：用这个端口，不再用 0
nohup dsh web --port "$PORT" > /tmp/dsh-dev-<任务名>.log 2>&1 &
sleep 8; grep -Eo 'http://127\.0\.0\.1:[0-9]+/\?token=[A-Za-z0-9_-]+' /tmp/dsh-dev-<任务名>.log
```

**端口为什么必须固定**：`--port 0` 每次启动都换端口，**旧 URL 全部失效**。现场表现是"你给我的地址打不开了"，
用户会以为进程挂了或插件坏了，而实际只是换了个端口。规则：

- 每个插件一个端口，**只挑一次**，存在私有 home 里（例如 `web-port`），以后每次都用它；
- 挑的时候**排除 3080**（主 GUI）；
- 端口被占用时**明确报错**并给出 `lsof -nP -iTCP:<port> -sTCP:LISTEN`，不要悄悄换一个——
  悄悄换等于又变回"每次都不一样"；
- 需要重新挑时用显式开关（`DSH_<插件>_PORT=0` 之类），不要靠删文件。

**URL 里的 `token` 仍然是每次启动生成的**（web 应用只有 `--host` / `--port` / `--public-url` / `--tls-*`，
没有固定 token 的开关）。所以"端口稳定"≠"URL 完全不变"：主机和端口稳定，`?token=` 会变。**不要把
稳定端口说成稳定 URL**；每次启动后从日志里取当次 URL 交给用户。

**为什么是持久，而不是每次新建**：会话、工作区选择、安装状态都在 `DSH_HOME` 里。每次新建 =
用户每次回来都看不到上一次的会话（实测反馈是“你是不是把会话弄丢了”）。删 home 只发生在
用户明确要求重置时。

**为什么不能是 `~/.dsh`**：主 GUI 正在写同一个 home，两个进程往同一份会话日志追加会损坏历史
（修法见 `dsh-session-repair` skill）。启动脚本应**结构性拒绝** `DSH_HOME == ~/.dsh`
（解析后比较，命中直接退出），不要依赖自觉，也别读继承来的 `DSH_HOME`——一个在会话里运行的
shell 往往已经 `export DSH_HOME=~/.dsh`，照用就会把插件装进用户主 profile。

**凭据**：私有 home 首次创建时可以从 `~/.dsh` **拷一次** `.env` / `.credentials.yaml` / 模型配置，
之后不覆盖。这是唯一允许的交叉点，且只读。

**不要从受限沙盒里的 shell 启动实例**（macOS）：seatbelt 不能嵌套。启动它的 shell 若已被沙盒化，
实例自己的 workspace-write 探测（运行时就是跑一次 `sandbox-exec -p '(version 1)(allow default)' true`）
会失败，dsh 判定后端不可用并按失败即拒绝处理——**agent 的每条命令都要向用户申请授权**，
现场很容易被误读成“这台机器沙盒坏了”。自检：在将要启动实例的 shell 里跑一次那条 `sandbox-exec`；
非 0 就先换一个不被沙盒化的环境再启动。

每条命令带**同一个** `DSH_HOME`（同一 shell 里也可以先 `export`）。URL 形如
`http://127.0.0.1:<固定端口>/?token=<…>`（实测 0.2.1-rc.1）——端口固定，**从日志取当次 token**，
不要猜、也不要在文档里写死。默认会打开本机浏览器，方便用户直接看；远程 / 无人值守加 `--no-open`。

**本地目录（link）的前置条件**：link 的真实路径在 profile 树外，官方包得从插件自己的
`node_modules` 解析（[13-gotchas.md](13-gotchas.md) 1、6）：

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

**是否复用已有 dsh-home**：

| 场景 | 做法 |
|---|---|
| 普通开发、加功能、修 bug | **复用**这个插件的私有 home（`~/.dsh-<任务名>`）；不要每次新建，否则会话全丢 |
| 现象依赖真实配置 / 会话 / 存储 | 从 `~/.dsh` **复制一份**到私有 home 再用（`cp -a ~/.dsh "$DSH_HOME"`，或只拷 `profiles/`、`data/`）——不要直接改真实 home |
| 用户要在自己环境里看 | 让用户自己装 / 起；agent 不在真实 `~/.dsh` 里试错——半成品会留在用户 profile 里 |

**每轮改动的循环**：改源码 →（有 client half）重建产物 → **重启这个 dev 实例**（Node half 默认没有
源码 watcher；"重装同版本"不是热更新，见「验证按改动面」表）→ 刷新页面 → 把本轮 URL 与测试点再发给用户。
同一时刻只给用户**一个**地址；**用户正在测的时候不要重启 / 换实例**（会打断他、丢失会话状态）。

**交接前自检**（否则用户看到的是一个"正常但没有插件"的界面）：

- 启动日志无 `failed to import` / `did not activate`；Plugins 页能看到本插件；
- 挂的是**正在开发的这份源码**（`readlink "$DSH_HOME/profiles/web/node_modules/<包名>"` 指向开发目录，
  不是旧副本 / 另一个 checkout）；
- 真调过一次工具 / 命令（不是只看了首页）；
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
