# 安装与验证详情

> **本文件回答**：安装通道、按改动面验证、负控、图标验收、排查顺序。**不回答**：发布与推广（→ 11 / 12）、纪律清单（→ 09）。

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
