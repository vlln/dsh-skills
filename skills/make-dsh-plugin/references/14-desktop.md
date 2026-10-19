# Desktop（Electron 宿主）

> **本文件回答**：在官方 DSH Desktop 上，插件怎么装、怎么调试、和 `dsh web` 有哪些差异。
> **不回答**：安装通道与验证方法（→ [10-install-and-verify.md](10-install-and-verify.md)）、UI 规格（→ [06-ui-style.md](06-ui-style.md)）、profile 机制（→ [02-profile-and-preset.md](02-profile-and-preset.md)）。

**来源**：官方 `apps/desktop/README.md`（应用行为、安装归属、运行时、恢复）、`packages/boot/plugin-manager` 与 `packages/client/ui-plugin-manager`（共享插件管理器）、`apps/cli/src/args.ts`（`desktop` profile 保留）；对照社区 README（`dsh-market`、`dsh-context`）里关于 Desktop 的安装说明。基线：master `0.2.1-rc.2` 文档，未在本机打包版逐条实测。

## 0. 一句话

**Desktop = Electron 壳 + 一整套 dsh Web 应用**（同一套 Host、同一个 Web 客户端、同一个插件管理器）。
**插件不用为 Desktop 写第二版**：client half 照常进 `__DSH_BOOT__`，Node half 照常跑在 Host 里。

差异只有四处：**装在哪、谁来管、版本跟谁走、怎么调**。

## 1. 安装：走应用内的插件页，不走 npm dsh

| 方式 | 能不能管 Desktop 的插件 |
|---|---|
| Desktop 里的 **Plugins 页**（共享 Web 插件管理器） | ✅ 首选；桌面版自带 pnpm，包操作不依赖 PATH |
| Desktop 自带的 `dsh` 命令（菜单「管理 dsh 命令…」） | ✅ 但要求：先启动一次 Desktop 初始化 profile → **完全退出应用** → `dsh plugin --profile desktop add <包>` |
| npm 安装的 `dsh` | ❌ 不能改 `$DSH_HOME/profiles/desktop`；CLI 也不能启动这个 profile |

- Electron 独占 `$DSH_HOME/profiles/desktop`（含包管理器状态与单实例锁）；`dsh --profile desktop` 会被启动器直接拒绝。
- **web 与 desktop 的安装互不相通**：装到 `web` 不会进 Desktop，装到 `desktop` 也不会进 `dsh web`——两个宿主各装一次。
- Desktop 的 `dsh.profile.bundles` = 内置 bundle + 已启用插件；**核心依赖不打进 profile**（打包在 `app.asar/dsh`），profile 只装外部插件。
- 安装路径按 [10-install-and-verify.md](10-install-and-verify.md) 的纪律验证；Desktop 不例外。

## 2. 版本：跟应用走，不跟 npm 走

- Desktop 把 **shell 与 `@deepseek-ai/dsh` 绑成同一精确版本**发布——升级 dsh 必须发新 Desktop 版本。
- 所以「用户装的 dsh 版本」在 Desktop 上等于**应用版本**，可能比 npm 上的旧或新。
- 用户报问题先确认应用版本（应用内「关于」）；README 的兼容性表要写清支持的 dsh 版本与验证日期，别写"最新版"。
- 在 Desktop 里验证插件时，用**应用自带的运行时**，不要用终端里另一个 `dsh` 去推断。
- 插件跨 dsh 大版本时，README 要给**宿主 × 插件版本**的对应表（旧 dsh 用旧插件版本），别指望一个版本通吃。

### 2.1 不要照抄 `dsh://plugin/install` 深链

社区 README 里出现过 `dsh://plugin/install?...` 的"Install in desktop client"按钮，但**官方 Desktop 只处理 `dsh://open`**（聚焦/唤回窗口）。把它写进安装说明会得到一个打不开的链接；Desktop 的正路仍是应用内 Plugins 页。

## 3. 调试：DevTools 是开着的

- `F12`（多媒体键盘 `Fn+F12`）、macOS `Cmd+Option+I`、Windows `Ctrl+Shift+I` 打开当前应用页面的 DevTools，**打包版也支持**。
- 能看 `__DSH_BOOT__`、client bundle 是否加载、`/plugins/<id>/client.js` 请求、`data-*` 属性与 console 报错——Web 上的排查手法照用。
- 例外：更新遮罩与打包版的内嵌浏览器**禁用** DevTools。

## 4. 文件与资源边界

- 应用资源在 **`app.asar`** 里：shell 命令、`node`、pnpm、search/glob 工具都**读不进去**（Creator/预设 skill 已注明这点）。
- 插件**自己的代码**不受影响：它从 profile 安装、由 Host/HTTP 提供，不在 asar 里。
- 插件 bundle 响应被标成 **`no-store`**（每次启动 revision 变化），别指望浏览器缓存旧 bundle。
- 写文件、读配置一律按普通 dsh 插件的方式，用官方服务；不要假设能直接读应用目录。

## 5. 语言（i18n）

- Desktop 的 preload 提供 `getLocale()` / `onLocaleChange(listener)`，bootstrap 里带 `zh_CN` 或 `en_US`；语言在首屏渲染前应用。
- **`ctx.locale` 的用法不变**；差别只在"宿主偏好从哪来"——Desktop 由原生壳给，浏览器按 `navigator` 回退。
- 插件 UI 仍按 [08-i18n.md](08-i18n.md) 走客户端字典；不要自己去读 Electron preload。

## 6. 启动失败与恢复

Desktop 的启动是**全有或全无**：一个第三方插件加载失败会进入原生恢复对话框，选项包括退出、重启、**禁用第三方插件**、备份 profile patch 后重启。

- 恢复会禁用第三方 bundle，并把 `cordis.patch.yml` 备份成 `cordis.patch.yml.bak-<时间戳>`，下次启动重建空 patch；**已安装包保留**。
- 也就是说：**插件把 Desktop 弄挂起不来**时，用户仍能通过恢复界面救回来；但这不能当作"随便写"的理由——装前仍要按 [10-install-and-verify.md](10-install-and-verify.md) 验证。
- 崩溃报告写到平台日志目录（macOS `~/Library/Logs/DeepSeek Harness`，Windows/Linux 在应用 `userData/logs`）。

## 7. 其他实测有用的差异

- **端口**：Desktop 默认监听**系统分配的端口**（避免与 `3080` 冲突），不要用 `http://127.0.0.1:3080` 当判据；应用内地址以启动页为准。
- **环境**：macOS/Linux 从图形界面启动时，Desktop 会跑一次登录 shell 读取环境变量（`DSH_DESKTOP_LOGIN_SHELL_TIMEOUT_MS` 可调）——插件依赖的环境变量可能来自 `~/.zshrc` 等文件；Windows 从注册表继承。
- **窗口**：关窗是**隐藏**，Host 继续跑（任务不中断）；"重启应用"与"重新加载插件"不是一回事，验证时区分。
- **第三方 Desktop**（社区 `dsh-desktop` 等）是另一套应用，不要与官方 Desktop 的行为混用；遇到问题先确认是哪一个。

## 8. 在 Desktop 上验证插件的清单

- [ ] 从应用内 Plugins 页安装成功（不是终端 `dsh plugin` 到别的 profile）
- [ ] 开 DevTools：`__DSH_BOOT__` 有本插件的 client 行，`/plugins/<id>/client.js` 有响应
- [ ] 真调一次工具/命令（boot 干净 ≠ 功能可用）
- [ ] 关掉再打开应用一次，配置与状态还在
- [ ] README 的兼容性一节写的是**应用版本**对应的 dsh 版本 + 验证日期
- [ ] 如果是 UI 插件：深浅色各看一次（Desktop 跟随系统外观）
