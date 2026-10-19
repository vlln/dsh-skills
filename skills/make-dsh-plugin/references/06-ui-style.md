# 插件 UI 风格（dsh Web 客户端）

> **本文件回答**：插件 UI 的 token / 控件 / 落位 / 交付自检（查阅型：按节查，不必通读）。**不回答**：设置页接线（→ 07）、UI 文案翻译（→ 08）。

Desktop 与 web 是**同一个 Web 客户端**（差异与调试见 [14-desktop.md](14-desktop.md)）。

给第三方插件作者：**把 UI 做进官方体系**——配色、圆角、字体、层级、控件选型与落位，
逐项给数值和判据。

**来源**：官方仓库 `deepseek-ai/deepseek-harness`——
`docs/web-styling.md`（样式归属与组件规则）、`docs/ui-radius.md`（圆角标准）、
`packages/client/ui-theme/src/styles/*`（token 值：base / corner-shape / design-platform / focus /
scrollbar / gradient-shadow-text）、`packages/client/ui-primitives/README.md`（组件目录与选型判据）
与同包 `src/*.tsx` + `*.module.css`（逐组件的 props 与几何）、`docs/subsystems/slots.md` 与
`packages/client/{ui-layout,ui-sidebar,ui-settings-plugins}` 的 README 与 `src/client/*.module.css`
（落位与外壳几何）、`packages/client/{ui-commands,ui-input-trigger}` 的源码（§10.7 命令行行外观
label / icon 与 `/` 菜单渲染）；另引用本 skill 的 [13-gotchas.md](13-gotchas.md)（实测坑）与
[07-settings-panel.md](07-settings-panel.md)（槽位注册写法）。
基线 **0.2.0-rc.2**（tag `dsh-v0.2.0-rc.2`，2026-10-15 逐条核）。**0.2.1-rc.1 复核**：token 名称与 §2.2 的解析值（bg / label / border / hover / menu）、§3 的圆角数值（4/8/12/16/20/28）与组件名（Button / SettingsForm / SettingsValueField / SegmentedControl / SegmentedTabs / Switch / Modal / Tooltip / Menu / Tag / Pill）一致；组件几何与逐条 props 仍按 0.2.0 标注。

- 官方那两份文档是写给 client 包维护者的规范，**本文件是插件作者的落地版**；冲突时以官方与
  **安装的运行时**为准（复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节——已装的官方包里就有
  编译后的 token 表与组件 CSS，可直接 grep）。
- **下面每节开头都标了该节的来源**，可以只挑一节溯源。

## 0. 四条铁律

> 来源：`docs/web-styling.md`「Ownership」与「Component rules」（样式归属、只消费语义 alias、
> 复用优先于重写、不定义第二套主题、保留焦点与 reduced-motion）＋ `docs/ui-radius.md`「Reuse tokens」。

1. **只消费语义 token**（`--dsw-alias-*` / `--dsw-specific-*`），不写死颜色，不抄 `--dsw-static-*` 的色值——
   写死的颜色在另一套主题里必然烂掉。
2. **能复用官方控件就复用**，不要抄第二份。控件唯一能跨包共享的地方是
   `@deepseek-ai/dsh-client-ui-primitives`（官方明确：插件不能 import 另一个插件的组件）；
   库内确实没有的语义（如"Enter 换行"的多行编辑）才自绘，并在代码注释里写明理由。
3. **不定义自己的主题**：不写 `body[data-ds-dark-theme]` 分支、不覆盖宿主主题变量、不加第二套色板。
   要扩展主题用官方 `ctx.theme` 注册（覆盖同名 alias）。
4. **尺寸也是契约**：圆角与高度配对（见 §3）、0.5px 发丝线（见 §5）、
   hover / 键盘焦点 / reduced-motion 都要保留。

## 1. 怎么把官方控件引进来

> 来源：`ui-primitives/README.md`（Use this package / Component catalog）；本 skill 的
> [04-plugin-contract.md](04-plugin-contract.md)（`dsh.client` 字段）与 [13-gotchas.md](13-gotchas.md) 10（平台种子模块的导出名会随 rc 改）；
> 构建形态取自实测参考实现 `vlln/whale-girl` 的 `scripts/build-client.mjs`。

包名 **`@deepseek-ai/dsh-client-ui-primitives`**，**没有子路径**——图标与控件同一条 import 路径
（`export * from './icons/index.tsx'`）：

```ts
import { Button, Switch, SettingsForm, IconRefreshOutlineRegular } from '@deepseek-ai/dsh-client-ui-primitives'
```

client bundle 沿用共享构建形态（与 `vlln/whale-girl` 同款）：

- esbuild 输出 **CJS**，把平台提供的模块打进 `external`：
  `--external:react`、`--external:@deepseek-ai/dsh-client-ui-primitives`（bundle 内留 `require(...)` 调用）；
- 外层包 `window.__ModuleLoader__.load({ id, factory: (require) => ({ name, inject, apply }) })`；
- `package.json` 的 `dsh.client` 里按需声明 `inject` / `external`（**不得声明自己**）。

⚠️ 平台种子模块表是 rc 相关的内部契约，**导出名会随 rc 改名**：`require()` 取到 `undefined`
不在导入时报错，要渲染时才炸（槽静默失效 + Minified React error #130）。落笔前先在**应用 bundle**
里核实名字存在，升级基线时把这些名字当回归点（见 13-gotchas.md 10）。

控件是**零 Cordis 的纯 props-in React**：没有 `ctx.locale` 兜底，所有面向用户的文案
（`label`、`*Label`、`labels` 对象）都必须由你提供。

## 2. 颜色

> 来源：`ui-theme/src/styles/design-platform.css`（static 调色板与 alias 的**全部声明值**，亮/暗两套）；
> token 的语义分工见 `ui-theme/README.md`（菜单 / toast / tooltip / switch / shimmer 等段落）。

### 2.1 三个词法层（只读最上面那层）

| 层 | 形态 | 谁能用 |
|---|---|---|
| `--dsw-static-*` | 设计平台导出的调色板（amber/blue/deepseek/green/neutral/neutral-bluish/red，亮暗各自一套值） | 主题层与官方插画；**插件不要直接用** |
| `--dsw-alias-*` | 语义别名（bg / label / border / interactive / state / button / markdown / scrollbar / code-diff） | ✅ 插件组件用这一层 |
| `--dsw-specific-*` | 特定用途（气泡、侧栏、菜单面、选择器、输入框、tip） | ✅ 落位到这些区域时用 |

主题切换**由宿主完成**：宿主在 `<body>` 上挂 `data-ds-dark-theme` 并同时设置 `color-scheme`；
`design-platform.css` 在 `body` 与 `body[data-ds-dark-theme]` 上各声明一套 alias 值。
插件只要消费 alias，**深色模式自动成立**。

### 2.2 常用 alias 速查

| 用途 | token | 亮色解析 | 暗色解析 |
|---|---|---|---|
| 页面底 | `--dsw-alias-bg-base` | `#fff` | `#151517` |
| 面板层 1/2/3 | `--dsw-alias-bg-layer-1/2/3` | `#fff`×3 | `#232324` / `#2c2c2e` / `#353638` |
| 设置卡填充 | `--dsw-alias-settings-card-fill` | = `bg-layer-2` | = `bg-layer-2` |
| 设置卡描边 | `--dsw-alias-settings-card-stroke` | = `border-l4` | = `border-l4` |
| 平台灰底（tag/selector） | `--dsw-alias-bg-module-platform` | `#f9fafb` | `#353638` |
| 主文字 | `--dsw-alias-label-primary` | `#0f1115` | `#f9fafb` |
| 次文字 | `--dsw-alias-label-secondary` | `#61666b` | `#cfd3d6` |
| 三级文字 | `--dsw-alias-label-tertiary` | `#81858c` | `#adb2b8` |
| 说明文字（caption） | `--dsw-alias-label-caption` | `#adb2b8` | `#81858c` |
| 反色前景（主按钮上的字） | `--dsw-alias-label-primary-foreground` | `#fff` | `#0f1115` |
| 链接 | `--dsw-alias-link` | `deepseek-500` | `deepseek-400` |
| 发丝线 l1→l4 | `--dsw-alias-border-l1` … `-l4` | 黑 4% / 10% / 12% / 16% | 白 6% / 12% / 16% / 20% |
| hover / active 底 | `--dsw-alias-interactive-bg-hover` / `-active` | `rgba(38,49,72,.06)` / `.10` | `rgba(255,255,255,.08)` / `.14` |
| hover 实底（不透明） | `--dsw-alias-interactive-bg-hover-solid` | `#f1f3f5` | `#353638` |
| 危险 hover | `--dsw-alias-interactive-bg-hover-danger` | 红 5% | 红 15% |
| 主按钮填充 / hover | `--dsw-alias-button-primary-fill` / `-hover` | `#0f1115` / `#43454a` | `#f9fafb` / `#ebedf2` |
| 信息按钮 | `--dsw-alias-button-info-fill` / `-hover` | `deepseek-500` / `deepseek-400` | `deepseek-400` / `deepseek-500` |
| ghost 选中面/边 | `--dsw-alias-button-ghost-active-fill` / `-border` | `#ebedf2` / `#979da6` | `#43454a` / `#81858c` |
| 成功 / 警告 / 错误 / idle | `--dsw-alias-state-success-primary` / `-warn-primary` / `-error-primary` / `-idle-primary` | `green-500` / `amber-500` / `red-600` / `neutral-300` | 同 / 同 / `red-400` / `neutral-600` |
| 业务强调（链接/引用/思考） | `--dsw-alias-state-business-primary` | `deepseek-500` | `deepseek-400` |
| 状态底（浅色填充） | `--dsw-alias-state-{success,warn,business}-tertiary` | 各自 100 阶 | 各自 800/900 阶 |
| 菜单面 | `--dsw-menu-surface-fill`（= `--dsw-specific-menu`） | `rgba(248,249,250,.58)` | `rgba(67,69,74,.45)` |
| 菜单图标 | `--dsw-alias-menu-icon` | `#353638` | `label-primary-dimmed` |
| toast 底 / 字 | `--dsw-alias-toast-bg` / `-label` | `#353638` / `#fff` | `#43454a` / `#fff` |
| tooltip 底 / 键帽 | `--dsw-alias-tooltip-bg` / `-key-bg` | `#2c2c2e` / 混合 18% 白 | `#43454a` / 同 |
| 输入主填充 | `--dsw-specific-input-major` | `#fff` | `#2c2c2e` |
| 气泡 / 高亮 | `--dsw-specific-bubble` / `-highlight` | `deepseek-50` / `-200` | `bluish-850` / `-750` |
| 侧栏底 / 项 hover / 项 active | `--dsw-specific-sidebar-fill` / `-nav-item-hover` / `-nav-item-active` | `#f9fafb` / `#f1f3f5` / `#ebedf2` | `#1b1b1c` / `#2c2c2e` / `#43454a` |
| 代码块 / 行内码 | `--dsw-alias-markdown-code-block` / `-inline-code` | `#f9fafb` / `#fafafa` | `#1b1b1c` / `#292929` |
| 骨架屏 | `--dsw-alias-bg-skeleton` | 黑 4% | 白 8% |

- **状态色的"浅底"不要自己调透明度**：`Tag` 等官方件的做法是
  `color-mix(in srgb, var(--dsw-alias-state-*-primary) 10%, transparent)`（`warning` 例外 12%）。
- `--dsw-alias-*` 声明在 `body` 上、深色覆写在 `body[data-ds-dark-theme]` 上——**自定义属性只向下继承**，
  所以引用它们的规则也要落在 `body` 之下的元素上（宿主 `scrollbar.css` 的文件头专门记了这个坑）。

## 3. 圆角（`docs/ui-radius.md` 的插件版）

> 来源：`docs/ui-radius.md`（角色表、嵌套几何、胶囊/圆的例外、设置卡材质）；
> 半径 token 的数值在 `ui-theme/src/styles/base.css`，超椭圆行为在 `corner-shape.css`。

H = 设计外高（含边框，`box-sizing: border-box`），R = `border-radius`。
**先定角色再定尺寸档**——宽度、标签长度、内容撑高都不单独决定更大的圆角。

| 角色 | 例 | R | token |
|---|---|---|---|
| 极小细节（H<20）：键帽、行内码 | | 4 | `--dsw-radius-xs` |
| 紧凑控件（H20–28）：小按钮、紧凑图标按钮、紧凑菜单项 | | 8 | `--dsw-radius-sm` |
| 标准控件/单行单元（H32–40）：按钮、输入框、选择器、导航行 | | 12 | `--dsw-radius-md` |
| 大控件/成组内容：大按钮、刻意多行的单元、嵌套表单组 | | 16 | `--dsw-radius-lg` |
| 独立内容卡：设置卡、消息气泡、引导条目卡 | | 20 | `--dsw-radius-xl` |
| 主包裹面：composer、对话框、主面板/浮层面板 | | 28 | `--dsw-radius-panel` |

- **具体默认**：`Button` 是 `sm` = H28/R8、`md` = H36/R12（outline 同）；
  标准 H32 输入框与 H36 选择器 = R12；代码块 / diff / 文件预览 = **R16**；设置卡与引导条目 = R20，
  R28 留给包裹它们的面板或对话框。**更高的卡片仍是卡片**，不要因为超过按钮高度就升到 R28。
- **不要引入 10/14/18/24px 这类档外字面量**；需要从真实内缩推导时用 `calc()`。
- **圆/胶囊要显式退出超椭圆**：`border-radius: 999px`（胶囊）或 `50%`（圆）必须**同一规则里**
  配 `corner-shape: round`，否则会被 `superellipse(1.5)` 压成方头/方块。官方 `Tag`/`Pill`/`Switch`
  都这么写。（全局圆角平滑由主题的 `corner-shape.css` 统一施加，插件不用自己开。）
- **嵌套几何**：同心内缩 `内 R = max(0, 外 R − 内距)`（R16 卡 + 4px 内距 → 内 R12）；
  填充贴边时由外层拥有可见圆角（裁切或继承同角）；**独立子卡按自己的语义档**，不要机械地减父 padding。
- **嵌套悬停**：单独一块可点面把 hover 画在自己身上；贴边的伪元素/覆盖层必须与可见外壳同圆角同曲线，
  否则会在底色与描边之间留出月牙。
- **标准菜单** = 外 R16 + 4px padding + 项 R12；**紧凑菜单** = 外 R12 + 4px padding + 项 R8；
  `SegmentedControl` = 外 R12 + 4px 内缩 + 段/指示器 R8；`SegmentedTabs` = 外 R16 + 4px 内缩 + 段 R12。

## 4. 字体与排版

> 来源：`ui-theme/src/styles/gradient-shadow-text.css`（`--dsw-font-*` 阶梯与 `--dsh-content-font-*` 派生）
> 与 `base.css`（字族、等宽栈、动效）。

- 字族：`--dsw-font-family`（系统栈，含中文 PingFang/微软雅黑）；等宽 `--ds-font-family-code`
  （`SF Mono, JetBrains Mono, …`，**故意不挂裸 `monospace`**：Windows 中文会掉到 SimSun）。
  品牌文本另有 `--dsw-font-family-brand`（Montserrat）。
- **正文跟随用户字号设置**：宿主把 `--dsh-content-font-size`（10–22px，默认 14px）设在 `body` 上，
  Markdown 阶梯按它平移（`--dsh-content-font-delta`）；次级文字用
  `--dsh-content-font-size-secondary`（≤14 时 −1，>14 时 −2，默认 13px）。
  插件里凡是"正文/描述"字体都应读这对变量，而不是写 14px。
- 固定阶梯（与用户设置无关的 UI 字号）：

| token | 值 | 用途 |
|---|---|---|
| `--dsw-font-xl-24` | 600 24px/32px | 大标题 |
| `--dsw-font-l-20` | 500 20px/28px | 区块标题 |
| `--dsw-font-m-18` | 500 16px/28px | 卡片标题 |
| `--dsw-font-base-16` / `-strong-16` | 16px/24px（strong 500） | 正文大档 |
| `--dsw-font-s-14` / `-strong-14` | 14px/22px（strong 500） | **UI 默认正文** |
| `--dsw-font-xs-13` / `-strong-13` | 13px/20px | 次级说明 |
| `--dsw-font-xxs-12` / `-strong-12` | 12px/18px | 密集 UI（按钮小字、tag 邻域） |
| `--dsw-font-xxxs-11` / `-strong-11` | 11px/14px | 最小档（`Tag` 是 11px/17px、weight 500） |
| `--dsw-font-markdown-*` | h1 21px→base 14px 阶梯 / code 12px/19px、code-block 11px/19px | Markdown 与代码 |
| `--dsw-font-markdown-code-block-small` | 11px/16px | 工具行展开卡里的小号代码 |

- **字重**：官方设计里的 Figma `510` 一律落成 `font-weight: 500`（非可变字体对中间字重渲染不可预测）。
  常用档只有 400 / 500 / 600 / 700。
- 字号与行高**成对**使用上面的 `font` 简写变量，别只改 `font-size`。

## 5. 阴影、浮层材质与边框

> 来源：`gradient-shadow-text.css`（`--dsw-shadow-lv*` 与三档 elevation 的实际值、菜单 blur、mask blur）；
> `docs/web-styling.md`「Component rules」（抬升面 `border: 0`、菜单材质归主题、0.5px 中性线、链接样式）。

| token | 值/形态 | 用在 |
|---|---|---|
| `--dsw-shadow-lv1` | `0 2px 4px 0 rgba(0,0,0,.05)` | 轻浮起 |
| `--dsw-shadow-lv1-blur` | `0 4px 12px 0 rgba(0,0,0,.02)` | |
| `--dsw-shadow-lv2` | `0 4px 12px 0 rgba(0,0,0,.02), 0 2px 8px 0 rgba(0,0,0,.04)` | 卡片 |
| `--dsw-shadow-lv3` | `0 0 1px 0 rgba(0,0,0,.2), 0 0 4px 0 rgba(0,0,0,.02), 0 12px 32px 0 rgba(0,0,0,.08)` | 强浮层 |
| `--dsw-elevation-stroke` | `0 0 0 0.5px var(--dsw-elevation-stroke-color)` | 发丝描边层 |
| `--dsw-elevation-panel` | stroke + `0 3px 8px 0 rgba(0,0,0,.03), 0 0 16px 0 rgba(0,0,0,.02)` | 面板、菜单、浮层 |
| `--dsw-elevation-prominent` | stroke + `0 3px 8px 0 rgba(0,0,0,.04), 0 0 20px 0 rgba(0,0,0,.05)` | 需要突出的浮层 |
| `--dsw-elevation-soft` | stroke + `0 4px 16px 0 rgba(0,0,0,.03), 0 0 24px 0 rgba(0,0,0,.03)` | 输入框/composer（大模糊、低透明度） |
| `--dsw-elevation-stroke-color` | 描边颜色（默认 `border-l4`，暗色菜单重绑 `border-l3`） | 可重绑 / 可置 transparent |
| `--dsw-menu-backdrop-filter` | `blur(40px) saturate(150%)` | 菜单材质 |
| `--dsw-mask-blur` | `none` | 遮罩不做模糊 |

- **抬升面一律 `border: 0` + `box-shadow: var(--dsw-elevation-*)`**：0.5px 发丝描边是阴影的第一层，
  因此**绝不要**再给它配 `--dsw-alias-border-*` 边框（官方 elevation 门禁会拒这种配对）。
  状态色边框（warn 面板）是真边框，保持 `1px`。
- **菜单一律用 `Menu` 或把自定义内容包进 `MenuSurface`**：材质（`--dsw-menu-surface-fill` +
  `--dsw-menu-backdrop-filter`）由主题拥有，插件**不得覆盖**这两个值。
- Modal 遮罩用半透明深色**不做模糊**（`--dsw-mask-blur: none`）。
- 用 `--dsw-specific-menu` 填充的浮层要同时加 `backdrop-filter: var(--dsw-menu-backdrop-filter)`
  并放在自己的隔离层上（否则嵌套菜单/固定定位会失真）；macOS 上该 fill 接近 94% 不透明。
- **中性边框与分隔线一律 0.5px**（按钮、输入框、卡片、行分隔、菜单分隔线、`hr`、竖轨）——
  Chromium 会把它画成 1 设备像素；虚线提示与状态色边框保持 `1px`。
- 可点链接（正文锚点、文件提及、web 来源、产物 chip）：`color: var(--dsw-alias-link)` +
  `font-weight: 500`，静止无下划线，hover/focus 用 3px offset 的**点线**下划线。

## 6. 焦点、动效、滚动条

> 来源：`ui-theme/src/styles/focus.css`（环宽与颜色表达式、指针模态抑制）＋ `ui-theme/README.md`
> 同段说明；缓动与时长在 `base.css`；滚动条重绑契约在 `scrollbar.css` 与 `ui-theme/README.md`
> 「Scrollbar rebinding」。

- **焦点环**：`--dsw-focus-ring-width`（2px，密集表格/工具栏可 1px）；
  颜色 `var(--dsw-focus-ring-color, var(--dsw-alias-state-business-primary))`
  （亮 `#4176E6`／暗 `#7AAAFF`）。要自绘时用同一表达式，包括后代与伪元素上的环。
  `focus.css` 只提供 `:focus-visible` 的**颜色与宽度**回退，**不提供 outline 样式**——
  自己写 `outline: none` 的控件必须自己画环。指针模态下宿主把非可编辑控件的环色置为透明
  （键盘导航恢复），插件不要自己判断模态。
- **动效**：`--ds-ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)`；
  `--ds-transition-duration: 0.2s`、`-fast: 0.1s`、`-slow: 0.3s`。
  自绘动画必须提供 `prefers-reduced-motion: reduce` 分支（官方件：关动画或保留静态基底）。
- **滚动条**：宿主已全局换肤，不要写组件级滚动条选择器。需要改时**重绑**这三个变量：
  `--dsh-scrollbar-thumb` / `-thumb-hover`（基础面绑 l1，抬升面绑 **l2** 对，另一合法目标是 `transparent`）、
  `--dsh-scrollbar-width`（默认 5px，需要对齐滚动条占用宽度时读它而不是写死）、
  `--dsh-scrollbar-thumb-border`、`--dsh-scrollbar-track-margin`（靠内缩做出更宽的可拖轨道）。

## 7. 自渲染 DOM 的落地纪律

> 来源：本 skill 的实测层——[13-gotchas.md](13-gotchas.md) 4（宿主覆盖注入样式）与 12（宽度手柄）；
> 图标命名/权重取自 `ui-primitives/README.md` 与 `src/icons/*`；插件图标见 [SKILL.md](../SKILL.md) Step 2b。

- **宿主可能清掉/覆盖注入的 `<style>`**（13-gotchas.md 4）：插件 UI 的**关键**样式用 JS 内联
  （内联优先级最高），别把成败押在 class 注入上。结构性样式可以走 CSS Modules。
- **不要锚官方 CSS Module 的哈希类名**（`wSkVaW_widthHandle` 这类，换版本就变）；
  给自绘视图挂**稳定的 `data-*` 属性**，用属性选择器定位与隐藏（例：新增 `conversation.view`
  页签会继承外壳的拖动宽度手柄 `[data-width-handle]`，用
  `:has([data-my-view]) [data-width-handle]{display:none}` 关掉，见 13-gotchas.md 12）。
- 图标：`Icon<名称><Outline|Fill>?<Regular|Medium>`，`Regular` = 1px 描边、`Medium` = 1.3px 同几何，
  `size` prop 控制渲染尺寸（各字形自持默认值，多为 16，少量 14/20/10）。
  颜色骑 `currentColor`，`aria-hidden` 是内置的——**无障碍名字归你**。
- 插件图标（Plugins 页识别用的那张）不是这里的图标组件：它是 `package.json` 顶层 `icon`
  指向的 36×36 自包含 SVG（见 [SKILL.md](../SKILL.md) Step 2b）。
- 减少重复：凡是"一行 + 可展开"的展示用官方 `DisclosureRow`（24px 紧凑行），
  凡是"大段只读文本"用 `MarkdownText`。

## 8. 控件目录（可直接复用）

> 来源：`ui-primitives/README.md` 的组件目录与「four pairs are easy to confuse」段落；
> 每个控件的 props / 几何 / token **逐条取自同包 `src/<组件>.tsx` 与 `<组件>.module.css`**；
> 导出情况核自 `src/index.ts` 与 `package.json#exports`。

下面每个控件都来自 `@deepseek-ai/dsh-client-ui-primitives`；标"未导出"的那些**从包入口拿不到**，只能自绘或走别的公开入口（如 `CodeBlock.toolbarLabels`）。

**"几何"给的是照抄用的数值**：直接 import 控件时这些已经生效；只有你要**自绘**同类部件（库内没有该语义）时，才照抄这些数值以保持同族外观。

### 8.0 选型速查

| 你的需求 | 用它 |
|---|---|
| 按钮（实心/幽灵/描边/工具条） | `Button`（不传 `variant` = 无框 ghost） |
| 单行输入（搜索框、内联表单） | `Input` |
| 勾选 / 两态开关 | `Checkbox` / `Switch`（可见标签自己放） |
| 少数互斥模式（需禁用语义） | `SegmentedControl` |
| 等宽受控 tab（视图切换） | `SegmentedTabs` |
| 插件配置页 | `SettingsForm` + `SettingsValueField`/`SettingsSecretField` + `SettingsFormModel` |
| 下拉 / 右键 / 子菜单 | `Menu`（自定义内容包 `MenuSurface`），分组用 `MenuGroup` |
| 居中对话框 / 敏感操作确认 | `Modal` / `RiskConfirmation` |
| 悬停预览（可停留、可选中、可复制） | `HoverCard` |
| 悬停或焦点提示 | `Tooltip`（要逃出祖先裁剪用 `portal`） |
| 顶部瞬态提示 | `Toast` |
| 原图预览模态 | `ImageLightbox` |
| 一行标题 + 可展开内容 | `DisclosureRow`（24px 紧凑行） |
| 只读徽标 / 可选胶囊 | `Tag` / `Pill` |
| 状态点 / 步骤圈 / 旋转 loader | `StateDot` |
| 进行中行的共享高光 | `TextShimmer` |
| 单行路径（保后缀） | `PathLabel` |
| 快捷键键帽 | `ShortcutKeys` |
| 文件类型图标 | `FileTypeIcon`（配 `classifyFileType`） |
| 连接中断/重连状态 | `ConnectionIndicator` |
| 命令输出 / 文件窗口 / diff / 搜索 / 网页 | `TerminalBlock` / `ReadBlock` / `DiffBlock` / `SearchBlock` / `WebBlock` |
| 只读 JSON（折叠面板 / 交互树） | `JsonBlock` / `JsonTree` |
| 助手 Markdown 正文 / 独立代码块 | `MarkdownText`（围栏自动走 `CodeBlock`）/ `CodeBlock` |
| 图标 | `Icon<名><Outline\|Fill>?<Regular\|Medium>`（同一 import 路径） |

### 8.1 表单与控件

包定位（README）：零 Cordis 的 React atom，颜色只走 `--dsw-*`；**插件不能 import 别的插件的组件，本包是控件的唯一共享处**——能套就套，把有意的视觉差异做进 prop，不要复制第二份。文案必须由调用方传入（atom 读不到 locale，缺参会类型报错，没有语言兜底）。

#### Button ｜ 可点击动作
- props：`variant?: 'primary'|'ghost'|'outline'|'toolbar'`（默认 `'ghost'`）、`size?: 'md'|'sm'`（默认 `'md'`）、`icon?`（前置 16px 槽）、`className?`、`children?`，原生 button 属性全透传；`ref` → 原生 `<button>`；默认 `type="button"`（传 `type` 可覆盖）。
- 几何：`md` H36 / R12（`--dsw-radius-md`）、字号 14px/LH22、padding 0 14px；`sm` H28 / R8（`--dsw-radius-sm`）、字号 12px/LH18、padding 0 10px；根 `gap: 4px`。
- token：primary→`--dsw-alias-button-primary-fill`（hover `--dsw-alias-button-primary-hover`，文字 `--dsw-alias-label-primary-foreground`）；ghost→**无静止底色**，hover `--dsw-alias-interactive-bg-hover`、active `--dsw-alias-interactive-bg-active`；outline→`0.5px solid --dsw-alias-border-l3`；toolbar→`--dsw-alias-button-tool-bar-fill` / hover `--dsw-alias-button-tool-bar-hover`；通用文字 `--dsw-alias-label-primary`；禁用 `opacity: .4` + `not-allowed`。
- 选用：不传 `variant` 得到的是**无框透明按钮**，要实心必须显式 `primary`。组件自身没有 `:focus-visible` 规则，焦点环来自主题全局规则。

#### Input ｜ 单行文本（搜索框、内联表单）
- props：`icon?`（16px 前置）、`className?`（**加在包裹的 `<span>` 上，不是 input**），原生 input 属性透传（不传 `type` 即 text）；`ref` → 原生 `<input>`。
- 几何：包裹层 H32、padding 0 8px、gap 6px、`--dsw-radius-md`；`<input>` 为 `flex: 1; min-width: 0`，字号 14px/LH22。
- token：边框 `--dsw-alias-border-l4`、底 `--dsw-alias-bg-layer-1`、前置图标 `--dsw-alias-label-tertiary`、文字 `--dsw-alias-label-primary`、`::placeholder` `--dsw-alias-label-dimmed`；聚焦 = 包裹层边框换 `--dsw-alias-state-business-primary`（**不用 focus-ring**）。
- 选用：只做单行；composer textarea 不属此 atom。README 注明 `Input` 与 `Pill` 都**没有设计稿来源**（自定义 atom），侧边栏那个相似的搜索框是消费方自绘的。

#### Checkbox ｜ 带 label 的受控原生勾选
- props：`checked`、`onChange(next: boolean)`、`label: string`（必填，渲染为可见文字并靠 `<label>` 包裹充当可访问名）、`disabled = false`、`title?`、`className?`。**无 forwardRef、无属性透传**（不能传 `id`/`name`/`data-*`/`aria-*`）。
- 几何：根 `<label>` inline-flex、gap 6px、字号 14px/LH20；方框 16×16、`margin: 0`。
- token：文字 `--dsw-alias-label-primary`；勾选色用浏览器原生 `accent-color: var(--dsw-alias-brand-primary)`；focus ring `--dsw-focus-ring-width`(2px) + `--dsw-focus-ring-color`（回退 `--dsw-alias-state-business-primary`），offset 2px；禁用 `opacity: .5`。
- 选用：需要 `data-modal-autofocus`/`id`/`name` 等属性时**必须自绘**——同包 `RiskConfirmation` 正是如此（自绘 16×16 + `accent-color: --dsw-alias-button-primary-fill`，注意与 atom 取的 token 不同）。禁用样式靠 `:has(input:disabled)`，源码无回退。

#### Switch ｜ 两态开关（36×20）
- props：`checked`、`onChange(next: boolean)`、`label: string`（必填，**只进 `aria-label`，不渲染可见文字**）、`disabled = false`、`title?`、`className?`。**无属性透传**。
- 几何：轨道 36×20、padding 2px、`border-radius: 999px` + `corner-shape: round`；滑块 16×16 圆形、开态 `translateX(16px)`、`transition: transform 120ms`。
- token：关态轨道 `--dsw-alias-border-l3`、开态轨道 `--dsw-alias-brand-primary`；滑块默认底 `--dsw-alias-label-primary-foreground`，关态换 `--dsw-alias-switch-thumb`（两主题都保持浅色）；禁用 `opacity: .5`；focus ring 同 Checkbox（offset 2px）。
- 选用：完全受控，点击只回调 `onChange(!checked)`、不自更新；外观由 `aria-checked` 选择器驱动；可见标签要自己在旁边放；`flex: 0 0 auto`，在 flex 行里不会被压扁。

#### SegmentedControl ｜ 少数互斥模式（tablist + 单个滑动块）
- props：`id`（派生 `<id>-<value>` 与它控制的面板 `<id>-<value>-panel`）、`value`、`options: readonly { value, label, disabled?, title? }[]`（JSDoc 要求 ≥2）、`onChange`、`label`（必填可访问名）、`disabled = false`（锁住每一段）、`className?`。
- 几何：轨道 `inline-grid`、段高 H28、段 padding 0 16px、gap 2px、轨道 padding 4px；外圆角 `--dsw-radius-md`、段圆角 `--dsw-radius-sm`；段字号 13px/LH20/weight 500；指示块位移 160ms（`prefers-reduced-motion` 下无过渡）。
- token：轨道底 `--dsw-alias-interactive-bg-hover`；指示块 `--dsw-alias-bg-layer-1` + `box-shadow: var(--dsw-elevation-soft)`（描边刻意 `border: 0`，藏在阴影里）；段文字 `--dsw-alias-label-secondary`，hover 与选中为 `--dsw-alias-label-primary`；禁用段 `opacity: .4`；focus ring `--dsw-focus-ring-width`/`--dsw-focus-ring-color`（offset -2px）。
- 选用：真互斥选项用它，一排各自开合的 chip 用 `Pill`。**面板由调用方渲染**并用 `aria-labelledby` 指回 tab；`onChange` **不会**回传已选值；键盘 ←→↑↓ + Home/End，跳过 disabled 段，焦点自动跟随。位置靠自定义属性 `--dsh-segment-count` / `--dsh-segment-index` 算术放置（前缀是 `--dsh-`，勿覆写；gap 与公式绑定）。

#### SegmentedTabs ｜ 等宽受控 tab（内部复用 Pill）
- props：`items: readonly [SegmentedTab, ...SegmentedTab[]]`（**非空元组**，每项 `{ value, label: ReactNode, id, panelId }`）、`value`、`onChange`、`label`、`className?`；返回 `ReactNode`，只出 tablist、不出面板。
- 几何：根 grid、padding 4px、`--dsw-radius-lg`、**无 gap**；列内联为 `repeat(n, minmax(0, 1fr))`；tab H34、padding 0 12px、字号 14px/LH20、圆角 `--dsw-radius-md`；指示块宽 `calc((100% - 8px) / n)`、`translateX(index * 100%)`、180ms。
- token：轨道底 `--dsw-alias-bg-module-platform`；指示块底 `--dsw-alias-bg-layer-3` + `0.5px solid --dsw-alias-border-l3`；tab 文字 `--dsw-alias-label-secondary` → hover/选中 `--dsw-alias-label-primary`，选中额外 `font-weight: 600`；`:focus-visible` 是**下划线**（`outline: none`、1px、offset 4px），不画环。
- 选用：**与 `SegmentedControl` 不是同一件事**——本组件不支持禁用（`SegmentedTab` 无 `disabled`/`title`），键盘只有 ←→ + Home/End（无上下键），点当前 tab **也会回调一次**（`SegmentedControl` 有「已选就不回调」守卫）。要禁用语义请改用 `SegmentedControl`；tab 按钮本身无法从外部加 class。

#### ConfigField ｜ 三合一配置输入（**包入口未导出**）
- props：`label`、`value`、`secret`、`choices: readonly string[]`、`disabled`、`overridden`、`invalid`、`labels: { reset, inherited, invalid }`、`onChange(value)`、`onReset()`（**全部必填**，无 `className`/`id`，`id` 由 `useId()` 生成）。
- 形态三选一：`choices.length > 0` → `select`（首项固定 `<option value="">{labels.inherited}</option>`，选空值触发 `onReset` 而非 `onChange`）；否则 `secret` → `<input type="password" autoComplete="new-password">`；否则 → `textarea`（`rows = clamp(换行数, 1, 8)`）。**优先级是 choices > secret**；空 choices + 非 secret 得到 textarea，不是单行 input。
- 几何/token：字段 flex column、gap 6px、padding 12px 0，相邻字段 `border-top: 0.5px solid --dsw-alias-border-l2`；控件 `padding: 6px 12px`、**无固定高度**、圆角 `--dsw-radius-md`、边框 `0.5px --dsw-alias-border-l4`、底 `--dsw-alias-bg-layer-3`、`font: inherit`，textarea 可垂直 resize；invalid 时 `[aria-invalid='true']` 边框与提示文字用 `--dsw-alias-state-error-primary`；重置按钮文字 `--dsw-alias-label-secondary`。
- 选用：**未从包入口导出**（全树仅自身内部引用，README 组件目录也未列出）——从 `@deepseek-ai/dsh-client-ui-primitives` import 不到它。

#### SettingsForm ｜ 插件设置页的框（正道）
- props：`labels: { unavailable, readOnly, saveFailed, save, saving }`（**五项全必填**）、`state: SettingsFormShell`、`onSave()`、`onDiscard()`、`children`。**没有 `className`**；组件自身不持有任何状态。
- 分支：`!state.available` → 整个表单换成 `<p role="status">`（**不渲染 children**）；`!state.writable` → children 上方加只读提示；`state.failed` → footer 里加失败提示；`state.saving` → 按钮文字换成 `saving`。
- 保存：按钮在 `!state.dirty || state.invalid || state.saving` 时禁用。几何：footer gap 8px / padding-top 16px；按钮 `padding: 5px 14px`、字号 13px、圆角 `--dsw-radius-md`，底色 `--dsw-alias-label-primary`、文字 `--dsw-alias-bg-layer-3`（**自绘按钮，不是 Button atom**，与 `.md` 的 H36/14px 不同）。token：只读/不可用文字 `--dsw-alias-label-tertiary`、失败文字 `--dsw-alias-label-error`。
- 语义：**只有保存会写**；离开页面即丢弃——卸载时自动调 `onDiscard`（每次渲染刷新 ref，故 `onDiscard` 无需 memo），且**不提供取消/丢弃按钮**。

#### SettingsValueField ｜ 暂存文本字段
- props：`Omit<SettingsFieldProps,'hint'>` + `hint?`、`help?: { label, content: ReactNode }`、`numeric?`、`placeholder?`；`SettingsFieldProps` 必填项为 `id`、`label`、`text`、`overridden`、`invalid`、`overriddenLabel`、`resetLabel`、`invalidLabel`、`disabled`、`onEdit(text)`、`onReset()`。**没有 `className`**。
- 渲染：label（`htmlFor=id`）+ 可选信息按钮（自持 `useState` 展开 `role="region"`，**不是 Tooltip**）；`overridden` 时右侧渲染 `Tag tone="neutral"` 徽标 + reset 按钮；`<input type="text">` 经 `id` 关联，`inputMode="numeric"` **仅当 `numeric === true`**，`aria-invalid` 仅在 invalid 时出现，`aria-describedby` 指向 `-message`/`-help`。
- 几何：字段 flex column、gap 6px、padding 12px 0，相邻字段 `border-top: 0.5px solid --dsw-alias-border-l2`（**放进非 `.field` 的包裹元素之间线就消失**）；输入框 **H34**、padding 0 12px、字号 13px、底 `--dsw-alias-bg-layer-3`、边框 `0.5px --dsw-alias-border-l4`、圆角 `--dsw-radius-md`。
- token：label `--dsw-alias-label-primary`；hint 与禁用文字 `--dsw-alias-label-tertiary`；invalid 边框与文案 `--dsw-alias-state-error-primary`；帮助按钮 hover 底 `--dsw-alias-bg-layer-4`；聚焦 = 边框换 `--dsw-alias-state-business-primary`（`outline: none`）。
- 边界：`numeric` 只写 `inputMode`，**不做任何过滤或校验**（合法性由字段 spec 的 `parse` 决定）；`id` 必填且须唯一（派生 `-help` 与 `-message` 两个 id）。它**不复用 `Input` atom**：自身 H34/13px/`--dsw-alias-bg-layer-3`，而 `Input` 是 H32/14px/`--dsw-alias-bg-layer-1`。

#### SettingsSecretField ｜ 只写凭据字段
- props：`Pick<SettingsFieldProps,'id'|'label'|'hint'|'text'|'disabled'|'onEdit'>` + `configured: boolean` + `stateLabel: string`。**没有** `overridden`/`invalid`/`resetLabel`/`overriddenLabel`/`invalidLabel`/`onReset`，也没有 `className`。
- 渲染：label + `.badges` 内 `Tag tone={configured ? 'neutral' : 'quiet'}`（**无条件渲染**，不同于 value 字段的 `overridden` 条件）；`<input type="password" autoComplete="new-password">`（显式拒绝浏览器保存密码自动填充）；底部 `<p>` 提示无条件渲染；不设 `aria-invalid`/`aria-describedby`。
- 语义：值不会随响应回来，只报告「是否已配置」；**空草稿不写任何东西**（保留已存 key，而不是清空）。

#### SettingsFormModel ｜ 暂存后保存的模型（设置页配套）
- 构造：`new SettingsFormModel(scope, specs, secrets = [])`；`scope` 需实现 `getSnapshot()`（含 `status: 'loading'|'ready'|'unavailable'`、`value`、`base`、`user`、`writable`、`revision`）、`subscribe()`、`mutate(ops, expectedRevision?)`。
- API：`bind(project)` 返回快照 store；`shell()` 给 `{ available, writable, dirty, invalid, saving, failed }`；`field(name)` 给 `{ text, overridden, invalid }`；`actions()` 给 `{ edit, resetField, save, discard }`；`save()`；`dispose()`。
- helper：`settingsNumberField(field)`——空串 → clear、非有限数 → 非法（`parse` 返回 `undefined`）；`settingsTextField(field)`——空串 → clear、否则 set（trim 后）。
- 语义：草稿暂存、保存时才写；**`overridden` 由字段在用户层「是否存在」判定**（不看值是否等于默认值）；保存未落地时保留草稿；`save()` 在不可写或存在非法草稿时直接返回不写；非法草稿仍算 `dirty`（会阻塞保存而非丢弃编辑）。

### 8.2 浮层、菜单与反馈

| 组件 | 用途 | 关键 props | 层级 |
|---|---|---|---|
| Menu | 锚定下拉菜单（数据行/组件行/子菜单） | `open` `anchor` `onClose` `items` `children` `portal` `selection` | 100；portal 1100；子菜单 101 |
| MenuSurface | 菜单材质层 + macOS 背衬 | `compact=false` + 透传 div props/ref | 材质层 −1 |
| MenuGroup | 菜单分组 + sticky 标题 | `label`；`observeStickyMenuGroups(viewport)` | 标题 1 |
| Modal | 居中对话框（body portal + 遮罩） | `open` `onClose` `title` `closeLabel` `headless` `backdropBlur` | 1000；卡内 1 |
| HoverCard | 可停留/可选中/可复制的悬停预览 | `anchor` `content` `variant` `inline` `openDelayMs=500` | 100 |
| Tooltip | 悬停/焦点气泡（克隆子元素做锚点） | `label` `side` `align` `delayMs` `focusDelayMs` `openOnClick` | 100；portal 1100 |
| Toast | 顶部居中瞬态横幅 | `text` `onDone` `holdMs=3000` `tone` `actions` | 1100 |
| ImageLightbox | 原图预览模态 | `src` `alt` `labels` `onClose` | 1000 |
| RiskConfirmation | 勾选门禁的敏感操作确认 | `open` `acknowledged` `onConfirm` + 全文案 | 继承 Modal（1000） |
| DisclosureRow | 24px 折叠行（标题与内容并排） | `icon` `title` `open` `expandable` `onToggle` | 无 |

#### Menu ｜ 锚定下拉菜单
- props：`open`/`anchor`/`onClose` 必填；`items=[]`、`children`、`footer`、`selectedId`、`selectedIds`、`onSelect(id)`、`align='start'`、`side='bottom'|'top'|'right'`、`portal=false`、`closeOnPointerLeave=false`、`dense=false`、`compact=false`、`autoFocus=false`、`selection='check'|'fill'`、`getAnchorRect`、`className`、`listClassName`
- 几何：卡片 `padding:4px`/`border:0`；标准 `min-width:144px`、`max-width:360px`，行 `min-height:34px`/`padding:6px 8px`/`gap:6px`/`13px:20px`；`compact` `min-width:156px`、行 `24px`/`2px 6px`/`11px:17px`；`dense` 行 `30px`、`padding-block:4px`；滚动上限 `calc(100vh - 12px - max(12px, var(--dsh-frame-overlay-top, 12px)))`（仅无子菜单行时加）
- token：`--dsw-elevation-prominent`（`--dsw-elevation-stroke-color` 重绑 `--dsw-alias-border-l1`）、`--dsw-alias-border-l2`（`.footer` 与 `.separator` 各 0.5px）、`--dsw-alias-menu-icon`、`--dsw-alias-interactive-bg-hover`、`--dsw-alias-interactive-bg-hover-danger`、`--dsw-alias-state-error-primary`、`--dsw-alias-label-primary/-tertiary/-caption`、`--dsw-radius-md/-sm`、滚动条 `--dsh-scrollbar-thumb(-hover)`
- 交互：↑/↓ 与 Home/End 环绕行走；Tab 结算焦点行、Shift+Tab 关闭并回锚点；Escape 走 capture 阶段（先于 Modal）关闭并归还焦点；外部 `pointerdown` 关闭；`closeOnPointerLeave` 走 200ms pointer grace；portal 定位 `MARGIN=12`、间隙 4，须给 `getAnchorRect` 才能摆脱 wrapper 测量竞态
- 选用：需要共享材质与键盘契约时用；材质圆角由 `MenuSurface` 提供，样式钩子只有 `className`（锚点包装）与 `listClassName`（卡片，portal 下唯一可达）；`MenuItemButton` 放进 `children` 共享行走与焦点归还，但**关闭始终由 owner 决定**；`side:'right'` 只对 portal 生效（原地 CSS 只有 sideTop/alignEnd）

#### MenuSurface ｜ 菜单材质层
- props：`compact=false`（仅改外圆角 lg→md）+ 透传全部 `div` props 与 ref（ref 指向可见 div，不含背衬）
- 几何：`border-radius: var(--dsw-radius-lg)`（compact → `--dsw-radius-md`）；`:where(.surface){position:relative}` 零特异性，调用方可覆盖为 fixed/absolute；材质层 `inset:0`、`z-index:-1`、`border-radius:inherit`
- token：材质 `--dsw-menu-surface-fill` + `backdrop-filter: var(--dsw-menu-backdrop-filter)`；背衬 `--dsw-alias-bg-base`；内联 `--dsh-menu-anchor`（`data-menu-material="translucent"`、`data-menu-backing`）
- 交互：无任何全局监听或滚动锁；背衬只在 `html[data-platform='darwin']` 显示（`position:fixed` + CSS anchor 跟随卡片），`aria-hidden`、`pointer-events:none`、随菜单卸载，且要求 Web shell 的隔离 body
- 选用：自定义菜单直接复用即得共享材质与圆角（feature 类只管布局与 elevation）；`compact` 必须同时作用材质层与背衬，否则圆角不一致

#### MenuGroup ｜ 菜单分组与 sticky 标题
- props：`MenuGroup{label: string, children?}`；`observeStickyMenuGroups(viewport: HTMLElement) => () => void`（清理断开 2 个 IntersectionObserver + 1 个 ResizeObserver、忽略排队回调、清 `data-stuck`；无有效分组则不获取 observer）
- 几何：标题 `position:sticky`/`top:0`/`z-index:1`、`padding:4px 7px 2px`、`font-size:11px`、`line-height:16px`、`font-weight:500`；`.group + .group{margin-top:3px}`；哨兵 `.start` 1px×1px 透明
- token：静止 `background:transparent` + `--dsw-alias-label-tertiary`；`[data-stuck]` → `--dsw-alias-menu-group-header-fill`（主题 94% 不透明）；非 darwin 标题 `--dsw-radius-md`
- 交互：`role="group"` + `aria-labelledby`（实例自有 id）；无键盘/焦点逻辑；`data-menu-group`、`data-menu-group-heading`、`data-menu-group-start` 为选择器契约；缺 IntersectionObserver/ResizeObserver 时标题保持 sticky 但透明
- 选用：自定义菜单与 listbox 共用，与 `Menu` 的 `items` 数据层无耦合；须渲染后从普通 effect 调用、容器无内边距/无边框、直接子节点是 MenuGroup；过滤等分组变化后必须重新 setup

#### Modal ｜ 居中对话框
- props：`open`/`onClose`/`title` 必填，非 `headless` 时 `closeLabel` 必填（`headless:true` 则 `closeLabel?: never`）；`description`、`children`、`footer`、`className`、`contentClassName`、`shortcutModal`、`onKeyDownCapture`、`backdropBlur=true`、`headless=false`
- 几何：root `padding: max(24px, var(--dsh-frame-overlay-top, 24px)) 24px`、`z-index:1000`、flex 居中；卡片 `width:min(380px,100%)`、`gap:20px`、`padding:0 0 24px`、`border:0`、`border-radius:var(--dsw-radius-panel)`；header `22px 14px 12px 24px`、title `16px:24px` w500、close `28×28`；description/body `padding:0 24px`，body `margin-top:20px`；footer `gap:8px` 右对齐
- token：遮罩 `--dsw-alias-bg-mask-1` + `backdrop-filter: var(--dsw-mask-blur)`（`inset: var(--dsh-frame-chrome-top, 0px) 0 0`）；卡面 `--dsw-alias-bg-layer-2` 配 `--dsw-elevation-prominent`；`--dsw-alias-label-primary/-secondary`、`--dsw-alias-interactive-bg-hover`；动画 `modalEnter var(--ds-transition-duration) var(--ds-ease-in-out)`，reduced-motion 关闭
- 交互：Escape/Tab 与焦点归属全交 `useModalLayer`（最顶层独占；Tab 过滤 `[inert]/[hidden]` 后循环；关闭归还先前焦点且不带外框）；`data-modal-autofocus` 标首焦点，**别用 React `autoFocus`**；遮罩点击即 `onClose`；`role="dialog"`+`aria-modal`+`aria-label={title}`；`data-shortcut-modal`；无滚动锁
- 选用：调用方已模糊页面时传 `backdropBlur={false}`；卡片限高必须用 `max-height:100%` 在这套 padding box 内表达，不要自己算视口；`headless` 去掉默认 header/close/body，但保留遮罩、卡片、Escape 与 aria-label

#### HoverCard ｜ 悬停预览（可停留/可选中/可复制）
- props：`anchor`/`content` 必填；`openDelayMs=500`、`disabled=false`、`variant='compact'|'preview'`、`inline=false`、`widthAnchorRef`；`copyText` 给了则 `copyLabel`/`copiedLabel` 必填（联合类型）
- 几何：`compact` 固定 `width:244px`、`padding:12px 16px`；`preview` 宽 `min(bounds.width−48, innerWidth−16)`、上下翻面与 `maxHeight`（上限 420）由 JS 算，视口边距 8、锚点间隙 8、左右内缩 24；`inline`（`.media`）`padding:8px`、`overflow:auto`；圆角 `--dsw-radius-lg`
- token：`.card` 背景 `--dsw-hovercard-bg`（**就地硬编码字面量，非主题 token**）+ `--dsw-shadow-lv3`；`preview` 改用 `--dsw-alias-bg-layer-1` + `--dsw-elevation-panel`；`inline` 用 `--dsw-specific-menu` + `--dsw-menu-backdrop-filter`；`--dsw-focus-ring-width/-color`（回退 `--dsw-alias-state-business-primary`）
- 交互：`z-index:100`，始终 portal 到 `document.body`；指针离开经 200ms grace（期间回到区域内只取消关闭、不重启 dwell）；`preview`/`inline` 支持 Escape（inline 会 `stopPropagation`，后续 Escape 到达 owner）；`inline` 由 `:focus-visible` 打开；`disabled` 立即收起；有 `copyText` 时卡片为 `role="button"`+`tabIndex=0`，Enter/Space 或点击复制、成功显示 `copiedLabel` 1000ms，存在非折叠选区时点击不复制；锚点内可见 tooltip 会撤回本卡
- 选用：需要随主题变色时选 `preview`/`inline`（`compact` 背景是本地字面量）；无语言回退，`copyLabel`/`copiedLabel` 必给

#### Tooltip ｜ 悬停/焦点气泡
- props：`label: string | (() => string)`（函数仅在可见时求值；空串只显示快捷键）与 `children`（单个元素，ref 被合并而非覆盖）必填；`shortcutKeys`、`side='right'|'bottom'|'top'`、`align='center'|'end'`（right 时忽略）、`delayMs=0`、`focusDelayMs=0`、`gap=8`（right 时忽略）、`disabled=false`、`portal=false`、`maxWidth`、`openOnClick=false`
- 几何：`padding:3px 7px`、`gap:8px`、`border-radius:var(--dsw-radius-sm)`、`13px:20px`、`width:max-content`、`max-width:50vw`、`white-space:pre-line`、`overflow-wrap:break-word`；right 侧锚点偏移 +10，视口边距 12；`[data-has-shortcut]` `padding-inline-end:5px`（无 label 时 `padding:3px`）
- token：`--dsw-alias-tooltip-bg` + `--dsw-static-neutral-bluish-00`；动画 `tooltip-in 150ms var(--ds-ease-in-out)`，reduced-motion 关闭（`z-index:100`，`[data-portal]` 时 1100）
- 交互：默认 `pointer-events:none`，仅 `[data-pinned]` 为 `auto`；**先隐藏**直到 ResizeObserver 给出 border-box 尺寸才 `visibility:visible`；只在"对侧放得下"时上下翻转；悬停与焦点是两个独立触发器（都清除才隐藏）；指针交互后的 focus 不举气泡（`pointerModality()`）；`openOnClick` 可点击钉住，再次点击/Escape/Tab/外部 pointerdown 关闭
- 选用：需要最高层叠保证用 `portal`（逃出祖先裁剪与 stacking context）；`shortcutKeys` 为空则不渲染键帽也不设 `aria-label`；`TooltipSuppression` 未从 `index.ts` 导出，插件从包入口拿不到

#### Toast ｜ 顶部居中瞬态横幅
- props：`text`/`onDone` 必填；`icon`（`tone='success'` 时忽略）、`tone?: 'success'`、`anchor?: HTMLElement | null`、`holdMs=3000`、`actions?: {label, prefix?, onClick}[]`
- 几何：`position:fixed`、`top:40px`、`left:50%`、`transform:translateX(-50%)`、`padding:12px 16px`、`gap:10px`、`border-radius:var(--dsw-radius-lg)`、`14px:22px`、`width:max-content`、`max-width:min(640px, calc(100vw - 48px))`、`z-index:1100`；`anchor` 给定时 `left = rect.left + rect.width/2`（window resize 重测）
- token：`--dsw-alias-toast-bg` + `--dsw-alias-toast-label`（两主题下都深色、固定不翻转）+ `--dsw-shadow-lv3`；图标 `--dsw-alias-state-warn-label`，success `--dsw-alias-state-success-primary`；动作 `--dsw-static-deepseek-400`；内联 `--dsh-toast-hold`
- 交互：`role="alert"`；body portal；表面 `pointer-events:none`，只有 `.action` 为 `auto`；卸载由 owner 在 `onDone` 中做，定时器 `holdMs + 1000`（FADE_MS 固定 1000，必须与样式表一致）；`holdMs` 不变时父组件重渲染不延长寿命；重显同一文案需按序号 key 重挂载
- 选用：`holdMs` 由 owner 按文案长度定；动画 `dsh-toast-in 160ms ease-out` + `dsh-toast-fade 1000ms ease var(--dsh-toast-hold, 3000ms) forwards`，reduced-motion 只保留淡出

#### ImageLightbox ｜ 原图预览模态
- props：`src`/`alt`/`labels{dialog, close}`/`onClose` 全必填；无 `open`——挂载即显示、卸载即恢复焦点
- 几何：`.backdrop` `position:fixed`/`inset:0`、`z-index:1000`、`padding:40px`、grid 居中；图 `max-width:min(100%,1600px)`、`max-height:calc(100vh - 80px)`、`object-fit:contain`、`border-radius:var(--dsw-radius-lg)`、`border:0`；关闭键 `36×36`、`top/right:20px`、`border-radius:999px`
- token：遮罩 `--dsw-alias-bg-mask-1` + `--dsw-mask-blur`；图面 `--dsw-specific-input-major` + `--dsw-elevation-prominent`；关闭键 `--dsw-alias-border-l2-darkmode-thin`、`--dsw-alias-label-primary`、`--dsw-focus-ring-width/-color`
- 交互：body portal；**不用 `useModalLayer`**——自有 window capture `keydown`：Escape `stopPropagation` 后关闭，Tab 一律 `preventDefault` 并把焦点强制回关闭键（单控件陷阱）；遮罩 `onMouseDown` 关闭；挂载记录 `activeElement`、卸载 `focus()` 归还；`role="dialog"`+`aria-modal`；无滚动锁
- 选用：挂载状态即开关状态；层叠刻意低于 Toast（1000 < 1100，源码注释说明失败提示须盖住预览）

#### RiskConfirmation ｜ 勾选门禁确认
- props：`open`/`title`/`description`/`acknowledgeLabel`/`cancelLabel`/`closeLabel`/`confirmLabel`/`acknowledged`/`onAcknowledgedChange`/`onCancel`/`onConfirm` 必填；`disabled=false`；`acknowledged` 受控
- 几何：卡片 `width:min(440px,100%)`、`max-height:100%`、`overflow:hidden`（`@supports (height:100dvh)` 时 `max-height:calc(100dvh - 48px)`）；内容区 `overflow-y:auto` + `overscroll-behavior:contain`；警告行 `gap:10px`/`14px:22px`；勾选行 `margin-top:20px`/`gap:10px`，复选框 `16×16`、`margin:3px 0 0`；按钮 `min-width` 72（取消）/136（确认）
- token：`--dsw-alias-state-error-primary`（警告图标）、`--dsw-alias-label-secondary`（警告文案）、`--dsw-alias-label-primary`、`--dsw-alias-button-primary-fill`（`accent-color`）、`--dsw-focus-ring-width/-color`
- 交互：复用 `Modal`，键盘/焦点全由 `useModalLayer`；`data-modal-autofocus` 落在复选框；`onCancel` 同时是 `Modal.onClose`（Escape/遮罩/关闭键统一走它）；主按钮在 `disabled || !acknowledged` 时禁用，`disabled` 也禁用复选框
- 选用：全文案 props 必填；`description` 由本组件在 `children` 内自行渲染（未走 `Modal.description` 席位）；限高契约已自行满足

#### DisclosureRow ｜ 24px 折叠行
- props：`icon`/`title`/`open`/`expandable`/`onToggle` 必填；`running=false`、`expandOnRowClick=false`、`previewChevron=expandable`、`keepContentWhenOpen=false`、`collapsedContent`、`children` + 类名槽 `className`/`rowClassName`/`contentClassName`/`contentLayoutClassName`/`leadingClassName`/`chevronClassName`/`titleClassName`
- 几何：行 `height:calc(24px + var(--dsh-content-font-delta, 0px))`、`overflow:hidden`；leading 盒 `calc(16px + delta)` 见方、`margin-right:6px`；行内 svg（除 `[data-state]`）`calc(14px + delta)`；标题 `font-size:var(--dsh-content-font-size-secondary, 13px)`、`line-height:calc(24px + delta)`
- token：`--dsw-alias-label-tertiary`（静止）→ `--dsw-alias-label-secondary`（悬停）；`--dsh-content-font-delta`、`--dsh-content-font-size-secondary`；过渡为字面量 `100ms ease`（颜色与图标透明度，reduced-motion 关行过渡）
- 交互：仅 `expandable && expandOnRowClick` 时行才有 `role="button"`+`tabIndex=0`+`aria-expanded`+行点击，键盘 Enter/Space 触发（`preventDefault`）；否则 leading 是带 `aria-label={title}`/`aria-expanded` 的按钮，其点击先 `stopPropagation()`；`data-open`/`data-disclosure-row`/`data-expandable` 为样式契约；无 Escape、无外层点击、无 portal、无滚动锁
- 选用：`memo` 浅比较，回调与 React 节点 props 必须稳定；`previewChevron` 默认跟随 `expandable`（悬停把图标换成下箭头，打开时为上箭头）；把名称与描述上下堆叠的卡片是另一种布局，不属此组件

#### hooks
- `useModalLayer(dialog, open, onClose): void` — 最顶层独占 Escape/Tab 与焦点；首焦点 `[data-modal-autofocus]` → 首个可聚焦元素 → 元素自身；配套 `closeTopModal(document)`（更新的菜单或未注册对话框会挡住）、`isBehindModal(anchor)`、`modalSelector = '[role="dialog"][aria-modal="true"], [role="menu"]'`
- `useAnchoredPosition({open, anchorRef, panelRef, side='bottom', align='start', gap, margin}): CSSProperties | null` — 返回 `{left, top}`，首次测量前为 `null`；夹取到 `[margin, innerWidth−width−margin]` 与 `[overlayTopMargin(margin), innerHeight−height−margin]`；订阅 scroll(capture)/resize/面板 ResizeObserver
- `useDismissOnOutsidePointer(root, open, setOpen, portal?)` — 仅 `open` 时挂 document `pointerdown`；target 不在 `root` 也不在可选 `portal` 内则 `setOpen(false)`

### 8.3 内容块（工具输出卡片）

**边界**：不要 import `CodeCard.tsx`——**源码中不存在**，只有 `CodeCard.module.css`（read/diff 卡片与代码 header 的共享样式表，非公开导出）；`CodeToolbar` 组件**未从 `index.ts` 导出**（只导出 `CodeToolbarLabels` 类型），复用代码 header 的唯一公开途径是 `CodeBlock.toolbarLabels` 或直接用 `ReadBlock`/`DiffBlock`。

**公共几何**：五张输出卡（Terminal/Read/Diff/Search/Web）统一 `white-space: pre` + 横向滚动，超过 `maxLines` 显示 head+tail 切片与展开按钮；切分算术 `hidden = total - maxLines`、`headLines = ceil(maxLines/2)`、`tailLines = 余数`。所有卡均为 `margin: 16px 0`、圆角 `--dsw-radius-lg`、背景 `--dsw-alias-markdown-code-block`、文案经必填 `labels` props 传入（包内无语言回退）。

#### 输出卡片

#### TerminalBlock ｜ 命令输出卡
- props：`command`（必填）、`output`、`cwd`、`home`、`exitCode: number|null`、`signal`（优先于 exitCode）、`running=false`、`maxLines=DEFAULT_TERMINAL_MAX_LINES`(16)、`copyText`、`runStateDot=true`、`labels`（13 项，全必填）
- 几何：`--dsl-terminal-line-height: 22px`、`--dsl-terminal-font: --dsw-font-markdown-code-block`、`--dsl-terminal-gutter: 30px`、`--dsl-terminal-radius: --dsw-radius-lg`；header `padding: 9px 14px 9px var(--dsl-terminal-gutter)`、`max-height: 150px`；output `padding: 12px 14px 12px 0`；正文行 `min-height: 22px`
- 可重绑：`--dsl-terminal-command-whitespace` / `--dsl-terminal-line-whitespace`（默认 `pre`，设 `pre-wrap` 换行）、`--dsl-terminal-gutter`（配 `runStateDot=false` 收回留白）、`--dsl-terminal-output-max-height`（配 `maxLines: Infinity` 用外部高度上限替代折叠）
- 选用：有 shell 命令与原始输出（含 ANSI）时用它；纯 markdown 回复用 `MarkdownText`，文件窗口用 `ReadBlock`。它**不是终端模拟器**（剥离绝对光标、清屏、备用屏）
- 颜色：`--dsw-alias-border-l2`（0.5px 横幅分隔）、`--dsw-alias-state-error-primary`（状态胶囊）、`--dsw-font-xs-13`（复制按钮）

#### ReadBlock ｜ 行号文件窗口卡
- props：`lines: readonly ReadBlockLine[]`（`{number, text}`）、`totalLines`（必填，用于 `lines.length < totalLines` 时的窗口注记）、`label`、`lang`、`maxLines=DEFAULT_READ_MAX_LINES`(16)、`labels: ReadBlockLabels extends CodeToolbarLabels`（+`window(shown,total)`、`copy/copied`、`collapse/expand` 及 aria）
- 几何：复用 `CodeCard.module.css` 的 `.card`；正文 `padding: 6px 22px 20px`；行 `min-height: 1lh`、`white-space: pre`；行号槽 `width: var(--dsl-read-gutter)`、`margin-right: 12px`、右对齐、`user-select: none`
- 可重绑：`--dsl-read-gutter`（内联为 `max(3, 最大行号位数)ch`）
- 选用：read 工具结果的带行号文件视图；无行号的纯代码片段用 `CodeBlock`，改动对比用 `DiffBlock`
- 行为：视口激活语法高亮、懒加载语法完成后自动重渲；复制只含行文本（`\n` 连接，无行号）、1000ms 反馈，`lines` 为空时禁用复制

#### DiffBlock ｜ 文件改动 diff 卡
- props：`diffs: DiffHunk[]`（`{path, oldText: string|null, newText}`；空数组渲染 `null`）、`maxLines=DEFAULT_DIFF_MAX_LINES`(16)、`labels: DiffBlockLabels`；另导出 `diffTotals(diffs): {added, removed}`
- 几何：复用 `.card` + 自身 `.block`(`overflow: hidden`)；正文 `padding: 6px 0 20px`、`display: grid`、`grid-template-columns: minmax(max-content, 1fr)`；行 `min-height: 1lh`、`padding: 0 22px`
- 可重绑：无专属 `--dsl-*` 变量；换行由工具栏切换 `data-code-wrap`（`minmax(0, 1fr)` + `pre-wrap`）
- 选用：一处或多处文件改动；只读代码展示用 `CodeBlock`，只读文件窗口用 `ReadBlock`
- 颜色：`+`/`-` 行用 `--dsw-alias-code-diff-added` / `--dsw-alias-code-diff-deleted` + `inset 3px 0 0` 侧条，文字 `--dsw-alias-state-success-primary` / `--dsw-alias-state-error-primary`；context/path 用 label-secondary，gap(`⋯`) 用 label-tertiary
- 行为：`context: 3` 行中性上下文、远距离改动用 `⋯`；单片段超 `MAX_DIFF_EDIT_LENGTH`(256) 行增删即按完整新旧内容粗粒度替换；复制含 `- `/`+ `/两空格前缀与折叠行

#### SearchBlock ｜ 搜索结果卡
- props：判别 `kind: 'matches'`（`files: SearchFileGroup[]`）或 `kind: 'paths'`（`paths: string[]`）；`truncated`、`total`（均必填）、`maxLines=DEFAULT_SEARCH_MAX_LINES`(16)、`labels`（含 `pathsSummary`/`matchesSummary`/`noResults`）
- 几何：**自有几何，不复用 CodeCard**——`--dsl-search-radius: --dsw-radius-lg`、`--dsl-search-line-height: 22px`、`margin: 16px 0`；header `padding: 9px 14px` + 背景 `--dsw-alias-markdown-code-block-banner`；body `padding: 8px 14px 12px 0`；行 `min-height: 22px`、`padding-left: 14px`；摘要/复制 `--dsw-font-xs-13`
- 可重绑：`--dsl-search-radius`、`--dsl-search-line-height`（与 `--dsl-terminal-*` 互不影响）
- 选用：grep/glob 工具结果；单文件读取用 `ReadBlock`，命令输出用 `TerminalBlock`
- 行为：文件头与 match 行**同样各占一行**参与折叠计数；折叠时尾部若从某文件中间开始会补挂该文件头（并消耗一个 tail 槽位保持 `hidden` 精确）；复制的是完整结构化结果（`path` + `行号: 文本`），不受折叠影响

#### WebBlock ｜ 联网检索卡
- props：判别 `kind: 'search'`（`answer`、`sources: WebSourceView[]`）或 `kind: 'fetch'`（`url`、`statusCode`）；`truncated`（均必填）、`labels`（含 `markdown: MarkdownLabels`，用于渲染 answer）
- 几何：`--dsl-web-radius: --dsw-radius-lg`、`margin: 16px 0`、`padding: 12px 14px`；来源列表 `padding-left: 2.5em`、`gap: 10px`、`max-height: 320px`（超出原位滚动）；链接 14px/20px、权重 500；摘要 13px/19px；fetch URL 用 `--ds-font-family-code` 13px/19px
- 可重绑：`--dsl-web-radius`
- 选用：`web_search` → `search`；`web_fetch` → `fetch`。非 http(s) URL 只渲染纯文本，不作 href
- 行为：`answer` 为空且无来源时显示 `labels.noResults`；`truncated` 分别显示 `sourcesTruncated` / `contentTruncated` 注记

#### 代码与 Markdown

#### CodeBlock ｜ 代码围栏卡
- props：`code`（必填）、`lang`、`streaming`、`lineNumbers=false`、`showHeader=true`、`copyLabel`/`copiedLabel`、`toolbarLabels`（传入才启用共享卡片 header 与间距）、`wrap`、`contentRef`、`className`
- 几何：`--dsl-code-block-border-radius: --dsw-radius-lg`、`--dsl-code-block-banner-font: 11px/18px var(--dsw-font-family)`、`--dsl-code-block-content-font: --dsw-font-markdown-code-block`、`--dsl-code-block-background`、`--dsl-code-block-banner-background-color: --dsw-alias-markdown-code-block-banner`；`margin: 16px 0`（非末位时 `margin-bottom: 11px`）；纯 `pre` `padding: 16px`；带 `toolbarLabels`（`.card`）时 `padding: 6px 22px 20px`；banner `padding: 9px 14px`、sticky；行号槽 `--dsl-code-block-line-number-width`（内联 `max(2, 行数位数)ch`，行内距 `+12px`）
- 可重绑：`--dsl-code-block-background`、`--dsl-code-block-banner-background-color`、`--dsl-code-block-banner-font`、`--dsl-code-block-content-font`、`--dsl-code-block-border-radius`、`--dsl-code-block-line-white-space`（`data-code-wrap='false'` 时置 `pre`）
- 选用：markdown 围栏（`MarkdownText` 对每个非空围栏都用它）；`lineNumbers` 只影响显示，**复制永不含行号**；代码围栏默认换行（`wrap` 未传时本地默认 `true`）
- 行为：流式围栏增量高亮，已完成行按 `STREAMING_LINE_GROUP_SIZE`(32) 分组；`code` 末尾单个换行会在显示时裁掉

#### JsonBlock ｜ 可折叠 JSON 面板
- props：`label`、`payload: unknown`、`defaultOpen=false`、`truncatedLabel: (total: number) => string`（必填）
- 几何：`margin: 4px 0`；toggle 12px/18px、`padding: 2px 6px`、圆角 `--dsw-radius-sm`；`pre` 体 `padding: 8px`、`max-height: 200px`、边框 `0.5px --dsw-alias-border-l1`、圆角 `--dsw-radius-lg`、`--ds-font-family-code` 11px/16px
- 可重绑：无专属 `--dsl-*` 变量
- 选用：会话侧的 JSON 值检视；结构化树形交互（逐行复制、键盘导航）用 `JsonTree`
- 行为：`MAX_CHARS`(20_000) 截断并追加 `truncatedLabel(完整长度)`；`JSON.stringify(payload,null,2) ?? String(payload)`，异常回退 `String(payload)`

#### MarkdownText ｜ 助手 Markdown 渲染
- props：`text`（必填）、`streaming=false`、`labels: MarkdownLabels`（`{code:{copyLabel, copiedLabel, toolbarLabels?}, footnotes}`；**必须引用稳定**，新 identity 会丢流式缓存）、`fileMentions`、`pathImages`、`variant: 'body'|'compact' = 'body'`
- 几何：`font: --dsw-font-markdown-base`；行内 code `--dsw-font-markdown-code` + `0.875em` + 背景 `--dsw-alias-markdown-inline-code` + `0.5px --dsw-alias-border-l1` + 圆角 sm + `padding: 0 5px`；`pre` `margin: 16px 0`；标题 h1–h3 `margin: 32px 0 16px`、h4 `16px 0`；`compact` 为 13px/20px（`--dsh-content-font-size-secondary` / `--dsh-content-font-delta-secondary`）、行内 code `1em` + 圆角 `--dsw-radius-xs` + `padding: 0 3px`
- 可重绑：无专属 `--dsl-*` 变量（代码围栏重绑经 `CodeBlock` 的 `--dsl-code-block-*`）
- 选用：不可信助手回复正文；工具输出卡片各归其类，不要塞进 markdown
- 行为：丢原始 HTML、仅允许 http(s)/mailto 链接；`fileMentions`/`pathImages` 只作用于结算渲染；`compact` 下代码块 banner 失去 sticky

#### JsonTree ｜ 只读 JSON 检视树
- props：`data`、`label`、`collapsedStringLines=3`、`stringWrapping?: {label, getDefault, setDefault}`、`copyable=true`、`expandTopLevel=true`、`labels: JsonTreeLabels`（10 项，全必填）
- 几何：`font: 12px/16px var(--ds-font-family-code)`、背景 `--dsw-alias-bg-layer-1`、`overflow: auto`；行 `min-height: 16px`、`padding: 0 0 0 10px`、`white-space: pre-wrap`；字符折叠高 `calc(var(--json-tree-collapsed-lines) * 16px)`（内联自 `collapsedStringLines`）；行内复制按钮 20×16、圆角 `--dsw-radius-xs`；展开字符串 `margin: 4px 0 0 12px`
- 可重绑：`--json-tree-collapsed-lines`（内联）、以及本文件自带的 `--json-tree-property/string/number/keyword/punctuation/icon/hover`（**非 `--dsw-*` token**，字面色值 + `body[data-ds-dark-theme]` 覆盖，宿主可用同名变量重绑）
- 选用：需要展开/折叠、键盘导航、逐行复制（值/路径/JSON）的结构化检视；简单折叠面板用 `JsonBlock`
- 行为：折叠字符串行数由 `collapsedStringLines` 与 `ResizeObserver` 实测决定；预览限对象 4 项 / 数组 5 项（`OBJECT_PREVIEW_LIMIT`=4、`ARRAY_PREVIEW_LIMIT`=5）、深度 2 层（`PREVIEW_DEPTH_LIMIT`=2）；复制反馈 1500ms（其他卡片为 1000ms）

#### 共享件（非公开 API）

#### CodeCard.module.css ｜ read/diff 卡片与代码 header 的共享样式表
- 无对应 tsx（**不存在 `CodeCard.tsx`**），由 `ReadBlock`/`DiffBlock`/`CodeToolbar` 内部导入；未从 `index.ts` 导出
- `.card`：`margin: 16px 0`、圆角 `--dsw-radius-lg`、背景 `--dsw-alias-markdown-code-block`、字体 `--dsw-font-markdown-code-block`
- `.header`：`padding: 10px 18px 8px 22px`、`background: var(--dsl-code-block-background, var(--dsw-alias-markdown-code-block))`、`font: 11px/18px var(--dsw-font-family)`、secondary；`.action` 24×24、圆角 `--dsw-radius-sm`、hover `--dsw-alias-interactive-bg-hover`
- `.body`：`padding: 6px 22px 20px`、`overflow-x: auto`（`DiffBlock` 用自有 `padding: 6px 0 20px`）
- 选用：不要当作公开样式表；需要一致外观请用 `ReadBlock`/`DiffBlock`/`CodeBlock.toolbarLabels`

#### CodeToolbar ｜ 代码卡片共享 header
- 未导出（`index.ts` 仅有 `CodeToolbarLabels` 类型）；props：`lang`、`title`、`status`、`labels: {codeLabel, wrapLabel, unwrapLabel}`、`copyLabel`、`copiedLabel`、`copied`、`wrapped`、`onCopy?`、`onWrap?`
- 几何：全取自 `CodeCard.module.css` 的 `.header`；图标 `size={14}`
- 行为：语言槽 `supportsHighlighting(lang) ? lang : labels.codeLabel`；换行按钮 `aria-label` 固定为 `labels.wrapLabel`、状态走 `aria-pressed={wrapped}`、图标在 `IconNowrapFillRegular`/`IconWrapFillRegular` 间切换；两按钮均包 `Tooltip side="top" portal`
- 选用：只能经 `CodeBlock.toolbarLabels`（或 Read/DiffBlock）获得

### 8.4 小原子、状态指示与图形

包名 `@deepseek-ai/dsh-client-ui-primitives`；零 Cordis，只经 `--dsw-*` token 取色；全部原子与图标同一导入路径（`import { Tag, IconChevronDownOutlineRegular } from '@deepseek-ai/dsh-client-ui-primitives'`）；用户可见文案一律由渲染方的必填 label props 传入。
#### Tag ｜ 只读胶囊徽标（11px，无 onClick/active）
- props：`tone?: TagTone='outline'`（8 值 outline/solid/neutral/quiet/success/info/warning/danger）、`className?`、`children?`；tone 落在原生 `data-tone` 上
- 几何：`padding:1px 8px`；11px/17px；`font-weight:500`；`border-radius:999px`+`corner-shape:round`；`white-space:nowrap`
- token：outline→`--dsw-alias-border-l4` 0.5px 边框+`--dsw-alias-label-tertiary`；solid→`label-primary` 底+`bg-layer-3` 字；neutral→`bg-module-platform`+`label-secondary`；quiet→仅 `label-tertiary`；success/info/warning/danger→`--dsw-alias-state-{success,business,warn,error}-primary` 经 `color-mix` 10% 填充（**warning 12%**）
- 选用：只读徽标用它；可选择胶囊或需坐 24px 文本行→`Pill`；同组只放一个 `solid` 标当前选中
- 复用：几何固定、只有配色变，渲染方自己的 class 可摆放而不碰配色
#### Pill ｜ 24px 行胶囊，可选（无 onClick 时是静态 span）
- props：`active?: boolean=false`、`className?`、`children?` + `ButtonHTMLAttributes<HTMLButtonElement>`（仅交互分支透传）
- 几何：`height:24px`；`padding:0 8px`；`gap:4px`；`border:none`；`border-radius:999px`+`corner-shape:round`；12px/18px
- token：底 `--dsw-alias-bg-layer-2` + `label-secondary`；`:hover`→`--dsw-alias-interactive-bg-hover`；active→`--dsw-alias-button-ghost-active-fill` + `inset 0 0 0 1px --dsw-alias-button-ghost-active-border`
- 选用：一排 `Pill` 是彼此独立、可同时 active 的 chip；互斥单选/箭头键 tablist→`SegmentedControl`；`TerminalBlock` 退出状态就是静态 `Pill`
- 复用：active 用 inset 阴影而非 border，不改变 24px 高；README 已知限制记 `Pill` 无设计源（`Input` 同）
#### StateDot ｜ 状态点 / 步骤圈 / ongoing loader（aria-hidden）
- props：`state: StateDotState` 必填（5 值 done/warning/ongoing/error/idle，**无 Active 变体**）、`size?`、`className?`、`appearance?: 'dot'|'step'='dot'`
- 几何：默认外径 ongoing 14 / 其余 10（`size ?? (state==='ongoing' ? 14 : 10)`）；`.dot::after` 用 `inset:20%` 画 6px `currentColor` 芯；`border-radius:50%`；`step` 为 `border:1.5px solid`，done 时内嵌 `IconCheckOutlineRegular size={edge-2}`
- ongoing：独立 SVG 分支，`viewBox 0 0 24 24`、r=9.5、`stroke-width:2`、track `opacity:.25`、arc `stroke-dasharray:12 150`；spin 1.5s linear + dash 1.5s ease-in-out 同周期；reduced-motion 关动画改 `18 150`/`-3`
- token：done/warning/error/idle→`--dsw-alias-state-{success,warn,error,idle}-primary`；spinner→`--dsw-alias-label-tertiary`；step→文字 `label-primary-foreground`、边框 `label-tertiary`，done/error 另填同色背景
- 复用：ongoing 忽略 `appearance`；实现把子动画 `startTime` 统一置 0，让同页不同时刻挂载的 loader 同相；`aria-hidden`，无障碍名由渲染方提供
#### TextShimmer ｜ 行内共享高光扫过（真实文本仍可选中）
- props：`children` 必填（不得含副作用/元素 id）、`active?: boolean=false`、`className?`、`contentClassName?`（同时作用于基底与装饰层）；组件为 `memo`
- 几何：根 `display:inline-grid; width:max-content; max-width:100%; min-width:0; vertical-align:top`；装饰层 `inset:0; overflow:clip; pointer-events:none; user-select:none`
- 动画：`animation-duration:1.5s`、`animation-delay:0.3s`、`steps(48,end)`、infinite；keyframe 在 `66.6667%` 到位（≈1.0s 扫过 + 0.5s 停留）；掩膜 `linear-gradient(105deg, transparent 0%, black 40% 60%, transparent 100%)`
- token：只有 `--dsw-alias-label-shimmer`（在 `.sweep` 上）；基色继承调用方 color，覆盖层强制 `.sweep *{color:inherit!important}`
- 选用/复用：图标和 chevron 放组件**外**；分隔符标 `data-shimmer-decoration` 才会被扫到；字符串子节点会被复制一份（装饰层用 `data-shimmer-text`+`::after`），复合子节点 active 时渲染两次；reduced-motion 隐藏装饰层只留静态基底
#### PathLabel ｜ 单行路径（目录弱化 + 文件名主色，溢出保后缀）
- props：`path: string` 必填 + `Omit<HTMLAttributes<HTMLSpanElement>,'children'|'title'>`；工具栏间距由调用方负责；`title` 自动取 `path`，调用方无法覆盖
- 几何：`display:flex; flex:1 1 auto; justify-content:flex-end; min-width:0; overflow:hidden; font-size:12px; white-space:nowrap`；内层 `flex:none; margin-right:auto`（放得下就左对齐，溢出时 auto 归零从而保后缀）
- 裁剪：JS 比较 `inner.offsetWidth > outer.clientWidth` 后置 `data-path-clipped`，配 `mask-image: linear-gradient(to right, transparent, black 28px)`；路径变化及 `ResizeObserver` 尺寸变化时重算
- token：`.directory`→`--dsw-alias-label-tertiary`；`.name`→`--dsw-alias-label-primary`
#### ShortcutKeys ｜ 键帽组（默认无框）
- props：`keys: readonly string[]`、`variant?: 'plain'|'tooltip'='plain'`、`className?`；不拥有绑定默认值与本地化文案
- 几何：plain 12px/16px、`gap:3px`，键帽无边框；tooltip 11px/14px、`gap:2px`，键帽 `min-width:16px; height:16px; padding:0 2px; border-radius:4px`
- token：plain 组 `--dsw-alias-label-tertiary`；tooltip 键帽与 `.joined` 底 `--dsw-alias-tooltip-key-bg`，tooltip 组 `color:inherit`
- 复用：`'+'` 是保留字符串，渲染为 separator 而非键帽；仅 `variant='tooltip'` 且 `keys` 含 `'+'` 时加 `.joined`（组合并入一个填充块，其内键帽背景透明、padding 归零）
#### FileTypeIcon ｜ 28px 分类着色文件/文件夹字形（纯装饰）
- props：`IconProps & ({ path: string; context?: FileTypeProjectContext } | { kind: FileTypeKind })` 二选一；`size? = 28`；色可用 `--dsh-file-type-icon-color` 覆盖；无无障碍名（调用方负责）
- `FileType` 全集：`CodeFileType | 'code'|'excel'|'folder'|'html'|'image'|'markdown'|'other'|'pdf'|'ppt'|'video'|'word'`；`FileTypeKind` 是给已解析分类的兼容别名；`path` 形式走 `classifyFileType`，`kind` 形式直接取用
- 另导出：`classifyFileType(path, context?)`（大小写不敏感；顺序 = 代码文件名→NAME_TYPES→EXTENSION_TYPES→`'other'`）与 `fileExtension(path)`（basename 最后一个点之后，无点返回空串）
- 几何：`viewBox="0 0 28 28"`；标记变换 `translate(14 16) scale(1.12|1.22) translate(-14 -16)`、folder 用 `translate(14 13.0693) scale(1.12)`；code 描边 1.35px、excel 1.2px、folder 横线 2.38px
- token：`.icon` = `color: var(--dsh-file-type-icon-color, var(--dsh-file-type-default-color))`；code/html/markdown→`--dsw-static-deepseek-500`；excel→`green-500`；folder→`amber-400`；image/video→局部 `--dsh-file-type-violet`；other→`neutral-bluish-300`；pdf→`red-600`；ppt→`amber-500`；word→`deepseek-450`；折角 `neutral-400`/`neutral-00`，标记组 `neutral-00`
- 选用：代码/配置文件走全彩 `CodeFileIcon`（**不受该覆盖影响**）；链接前图标用 `LinkIconMedium`，图片内容用图片预览；`md` 与 `svg` 仍是传统 markdown/image
#### ConnectionIndicator ｜ 内联连接恢复控件（三态）
- props 全必填：`state: ConnectionIndicatorState|undefined`（3 值 disconnected/connecting/recovered；`undefined` 表示开始退出）、`disconnectedLabel`、`connectingLabel`、`recoveredLabel`、`reconnectActionLabel`、`restartActionLabel`、`onReconnect: () => void`
- 几何：`display:inline-grid; grid-template-columns:14px max-content; column-gap:4px; height:28px; padding:0 8px; border:1px solid transparent`；12px/18px、weight 500、`border-radius: var(--dsw-radius-sm)`；图标槽 14×14；宽度随文案自适应
- 退出/动画：`EXIT_MS=150`，`.leaving{opacity:0}`，出现时 `indicator-enter 150ms`；`connecting` 的三个点每 500ms 推进一个（`1.5s step-end`，33.33%/66.66% 处翻到 opacity 1）
- token：warning→底 `--dsw-alias-state-warn-tertiary`、字 `state-warn-label`、边框 `color-mix(warn-label 20%, transparent)`，hover 混 `warn-primary` 6%、active 10%；success→`state-success-tertiary` + `state-success-primary`；focus-visible→`--dsw-focus-ring-width` solid `--dsw-focus-ring-color`（回退 `state-business-primary`）
- 选用：中断与重试共用一个按钮（静态文案已命名重试动作），点击请求立即重连；`recovered` 是唯一非按钮分支（`role="status"` + 勾）；`connecting` 复用 `StateDot state="ongoing"`；不使用原生 title
#### ImagePreview ｜ 被动受限图片预览（**未从包根导出**）
- props 全必填：`src`、`alt`、`loadingLabel`、`failedLabel`；换 `src` 即换 `key` 从而重新加载
- 几何：`.frame` `width:100%; height:180px; display:grid; place-items:center; overflow:hidden`；`.image` `object-fit:contain; opacity:0`（有 `data-ready` 才为 1）；`.status` 绝对铺满、`gap:8px; padding:12px; font-size:12px`
- token：`.frame`→`--dsw-alias-bg-base`；`.status`→`--dsw-alias-label-tertiary`；圆角 `--dsw-radius-sm`
- 选用/约束：包内仅被 `markdown/render.tsx` 使用，插件无法从包根 import；内置 `loading="lazy"`/`decoding="async"`/`referrerPolicy="no-referrer"`；刻意不引入第二个激活目标
#### projectUserText ｜ 已发送用户文本的内联投影（user-text.tsx）
- 签名：`projectUserText(text, sessionLabels: readonly string[], slashNames: readonly string[] = [], slashKind: 'skill'|'command' = 'skill', references?: UserTextReferences): ReactNode`
- `UserTextReferences = { openFile(path); openSkill(name) }`；只有 file 引用且提供了 `references` 时才渲染 `<button>`，skill 引用仅在 `slashKind='skill'` 时可点，session/command token 永不是按钮
- 装饰四来源（按优先级）：线协议 `@[label](dsh-session:…)` 折成 label；相邻 recall 给的精确会话 label 装饰其裸 `@label`；按形状匹配的裸 `@name`；仅调用方点名的 `/name`
- 边界规则：`@name` 去掉句末标点 `[.,;:!?，。；：！？]`；`/` token 以空白为界，故 `/123`、`/nfs-hg/xxx`、`/plan。` 保持纯文本；`label.length<=1` 跳过
- 结构/token：chip `display:inline`（**非 inline-flex**，否则 flex 基线会让 label 高约 3px）、`margin:0 2px`、`font-weight:500`、`overflow-wrap:anywhere`；色 `--dsw-alias-state-business-primary`；`/` chip 用 `--dsw-font-markdown-code-font-family`；图标 `ReferenceIconRegular size=16`，尺寸 `1em` + `vertical-align:-0.125em`
#### PluginArtwork* ｜ 固定调色板插件插画（36×36）
- 5 个导出均为 `({ size = 36, className }: IconProps)`：`Terminal`（插件卡片/侧栏引导的浅蓝提示符）、`Loop`、`Subagent`（也标记 bundle 内每一行）、`Search`、`Default`（无自己插画时）
- 不走 `--dsw-*` token（自带品牌色与渐变）；带渐变的必须用 `useId` 派生的每实例 def id，否则同页重复时 `url(#…)` 全指向第一个；`Search` 靠 `foreignObject` + CSS `conic-gradient`，不能用于 `<img>`/mask
#### GuideArtwork* ｜ 侧栏引导条目固定调色板插画（36×36）
- 2 个导出均为 `({ size = 36, className }: IconProps)`、`viewBox="0 0 36 36"`：`GuideArtworkBrowser`、`GuideArtworkFiles`；两者写死 `aria-hidden="true"`，只能作纯装饰、不能承载信息
- 不走 `--dsw-*` token（固定字面量色值）；无渐变、无 def id，因此不需要 `useId`
#### 图标系统（`Icon*Regular` / `Icon*Medium`）
- 规模：188 个导出 = 94 对（纯填充的对两者渲染完全相同）；**尺寸中性**——命名不含画板尺寸，`size` prop 决定渲染尺寸
- 命名：`Icon<名><Outline|Fill>?<Regular|Medium>`；`Regular` = 1px 描边，`Medium` = 同一几何 1.3px 描边；props 为 `IconProps { size?: number; className?: string }`，颜色一律骑 `currentColor`，除 artwork 外都 `aria-hidden`
- 默认 `size` 由各字形自持：16px 71 个、14px 15 个、20px 2 个（Archive/Unarchive）、10px 1 个（TreeCorner，非正方形 `width = size*8/10`，viewBox 9×11）
- 画板非全 16：16×16 为主，另有 17×17（Skill、AlarmClock）、14×14（Info）、20×20（Unarchive）、36×36（CheckCircleFill，默认仍 16）
- 代表名：导航 `IconChevronDown/Left/Right/UpOutline`、`IconChevronsUpDownOutline`；动作 `IconPlus/Copy/Trash/Refresh/Search/Settings/Edit/PaperclipOutline`；状态 `IconCheckOutline`、`IconCheckCircleFill`、`IconWarningOutline`（圆）、`IconWarningTriangleOutline`（圆角三角）、`IconInfoOutline`、`IconLoadingOutline`；面板 `IconPanelLeftOutline`、`IconCompactOutline`、`IconWrapLinesOutline`/`IconNowrapFill`/`IconWrapFill`、`IconEllipsisOutline`；会话 `IconNewChatOutline`、`IconThinkOutline`、`IconPlanOutline`（默认 14）、`IconSkillOutline`；主题 `IconLight/Dark/FollowsystemOutline`
- 本组其它原子的依赖：`StateDot`→`IconCheckOutlineRegular`；`ConnectionIndicator`→`IconCheckOutlineRegular`/`IconRefreshOutlineRegular`；`ImagePreview`→`IconLoadingOutlineRegular`

## 9. 落位与容器对齐

> 来源：`docs/subsystems/slots.md`（槽位层级与 cardinality/scope）；
> `packages/client/{ui-layout,ui-sidebar,ui-settings-plugins}` 的 README 与 `src/client/*.module.css`
> （外壳几何、设置页与侧栏的具体数值）。

槽位 key 的**选择与注册写法**见 [07-settings-panel.md](07-settings-panel.md) 与官方 `docs/subsystems/slots.md`；这里只讲"放进那个位置之后要照抄什么"。
本节形如 `SidebarRoot.module.css:9-14` 的引用都在官方仓库
`packages/client/<包>/src/client/` 下（`ui-sidebar` / `ui-layout` / `ui-settings-plugins` …），
`*.tsx:NN` 同理。

### 插件相关槽位表

| 槽位 key | 放什么 | cardinality/scope（快照内可证的才写，其余「未确认」） |
|---|---|---|
| `sidebar.panellist` | 全局面板图标组件；必须带 `id`（+可选 `order`、`label`） | `list` + `root`（ui-sidebar/README.md:38） |
| `sidebar.brand.mark` / `sidebar.brand.name` | 品牌图记 / 名称；接受 `{ size }`，无占据者回落 FishLogo | `single`（ui-sidebar/README.md:34）/ scope 未确认 |
| `sidebar.toggle.badge` | 折叠按钮内的非交互状态徽标 | 未确认 |
| `sidebar.workspaces` | Workspace/Session 浏览器；owner props `{ wide, expandSidebar }` | 未确认 |
| `sidebar.settings` | 设置触发器 + 整个设置面板；owner props `{ wide }` | 未确认 |
| `sidebar.footer.action` | 设置座**之上**的底部动作按钮 | 未确认 |
| `main` | 全局面板页；`renderSlot` 用 `{ entryKey: panelId ?? 'conversation' }` | `keyed` + `root`（ui-layout/README.md:32） |
| `settings.section` | 一个设置页；被设置壳投影成导航条目 | 未确认（README 称 ledger） |
| `settings.plugins.tab` | Plugins 页一个本地化页签；注册需 `id`+`order`+`label` | `list` + `root`（ui-settings-plugins/README.md:40） |
| `settings.trigger` / `.header` / `.action` / `.close` / `.onboarding` | 设置触发 / 标题栏 / 头部动作 / 关闭 / 引导步骤 | 未确认 |
| `plugins.item` / `.bundle.config` / `.row.config` / `.detail.actions` / `.detail.badge` / `.detail.section` | 插件管理器列表条目、bundle 详情配置、行配置、详情动作/徽标/分区 | 未确认（`.bundle.config` 文字描述为按 npm 包名 keyed） |
| `plugins.bundle.activation` | 启用 bundle 后的引导（含 dismiss / 打开详情回调） | 未确认 |
| `conversation.session` | 会话主体 | 未确认 |
| `conversation.input.activity` | composer 条上、模型选择器与 Send 之间的单个动作 | 未确认 |
| `shell.leading` | macOS 侧栏全隐藏时的窗口 chrome 座 | `single` + `root`（ui-layout/README.md:37） |
| `shell.overlay` | 覆盖全框架的浮层 | 未确认 |

列表渲染用 `{ only: id }`，keyed 用 `{ entryKey }`，单例可给 `{ fallback }`（SidebarRoot.tsx:71,189 / AppFrame.tsx:42）；`main` 选中未注册条目抛错并保持原选择（ui-sidebar/README.md:38）。

### 容器几何

- 侧栏：264–420px，默认 280px，折叠 rail 56px，<1024px 自动折叠（ui-layout/README.md:30）。
- 侧栏根 `padding: 6px 12px`（`--dsh-sidebar-inline-padding: 12px`），折叠 `padding: 18px 10px 6px`（SidebarRoot.module.css:9-14,34-36）。
- 侧栏行：logoRow 60px（折叠 36px）、topStrip 52px、newSession 38px/R12/`padding 8px 12px`、panelRow `min-height 36px`/`padding 7px 8px`/R12/`gap 8px`、iconButton 28px（折叠 36px）、panelList `gap 4px`,`margin-bottom 8px`（折叠 12px/12px）（SidebarRoot.module.css:220-231,443,493-509,318-350,483-542）。
- 分隔线：左列 `border-right: 0.5px solid var(--dsw-alias-border-l3)`；macOS 改到中列 `border-left`（AppFrame.module.css:63-68,157-160）。
- 中列：`min-width:0` + flex column + `overflow:hidden`；保护宽 400px（AppFrame.module.css:70-75 / ui-layout/README.md:30）。
- 设置页 `.section`：flex column，`gap: 12px`，`max-width: 760px`；`.heading` 18px/600；`.intro` 13px；`.tabs` `align-items:flex-end`/`gap:22px`/`border-bottom 0.5px var(--dsw-alias-border-l2)`/`margin-top:2px`；`.tab` `padding 7px 1px 9px`,13px/20px；选中下划线 `height 2px`/`radius 2px 2px 0 0`/`bottom -1px`；`.panel` `min-width:0`,`padding-top:2px`（PluginsSettingsSection.module.css:3-70）。
- 顶部净空：`--dsh-frame-top-clearance` 48px（darwin）/ Windows caption 高度；`--dsh-frame-overlay-top` = 净空+20px（全屏 20px）；`--dsh-frame-leading-clearance` 160px（darwin 折叠）/ 全屏 84px（AppFrame.module.css:93-113,183-194）。
- `shell.leading` 座：`absolute top 11px left 88px z-index 15`（全屏 `left 12px`）；按钮 28px/R8、`gap 8px`（AppFrame.module.css:212-220,196-198 / HeaderLeadingControls.module.css:6-25）。
- 圆角：`--dsw-radius-sm` 8px、`-md` 12px、`-lg` 16px；Windows 内容左上 16px（base.css:16-21 / AppFrame.module.css:27,34-38）。
- 层：拖拽手柄 8px 宽/`margin-left -4px`/`z-index 11`；leading 15；overlay 20（子元素恢复 `pointer-events:auto`）（AppFrame.module.css:228-237,216,277-286）。
- 设置卡片：`--dsw-alias-settings-card-fill` / `--dsw-alias-settings-card-stroke`（base.css:25-26）。焦点环统一 `var(--dsw-focus-ring-width)`（2px）+ `var(--dsw-focus-ring-color, var(--dsw-alias-state-business-primary))`（focus.css:3）。

### 插件在这里放 UI 时的对齐要求

1. `sidebar.panellist`：接受 `{ size, active }`（展开 16 / 折叠 18，SidebarRoot.tsx:71），同一 `id` 必须同时在 `main` keyed 注册页面。
2. `main` 面板页：入口页顶部自 pad `--dsh-frame-top-clearance`；内容触左上角再 pad `--dsh-frame-leading-clearance`。
3. 浮层/对话框顶部用 `--dsh-frame-overlay-top`；`shell.overlay` 层本身 `pointer-events:none`，子元素自己恢复。
4. `sidebar.footer.action` / `sidebar.settings`：座只给 `{ wide }` 与 flex 容器（`width:100%`，折叠时居中 `width:auto`），按钮几何与 hover 自带；设置座折叠时只淡出、不位移。
5. `settings.section` 页：卡片照抄 settings-card 双 token；内容宽度受 760px 限。
6. `settings.plugins.tab`：注册 `id`+`order`+`label`；内容渲染进 `.panel`，故纵向间距自备；单页签不渲染 tablist；页签用 `hidden` 保留挂载，要容忍隐藏但仍挂载。
7. `shell.leading`：位置/净空归框架，占据者可无条件渲染；按钮自带 `no-drag`，节奏 8px。
8. `rightbar`：占据者自报 `{ width, viewportWidth, canShow }` 并自绘左边界（右列不裁剪）（AppFrame.tsx:286）。
9. 折叠中途的 `wide` 语义：Windows 为 `!collapsed`，其他平台为 `!collapsed || !settled`，需容忍「已折叠但按宽布局渲染」（SidebarRoot.tsx:112-113）。
10. 侧栏列滚动条默认 l2 对；指针离开列即被重绑为 `transparent`（布局预留仍在）（SidebarRoot.module.css:19-22,121-132）。

## 10. 常见插件形态的配方

> 来源：`docs/ui-radius.md`「Settings card materials」＋ [07-settings-panel.md](07-settings-panel.md)（槽位与写入语义）
> ＋ 本文件 §8（控件）＋ 官方 `ui-commands` / `ui-input-trigger` 源码（§10.7 的命令行行外观 label / icon）
> ＋ 实测参考实现 `vlln/whale-girl` 的决策记录（自绘控件的返工教训）。

### 10.1 设置页卡片（插件配置面）

- **控件全用官方的**：`SettingsForm` 做框、`SettingsValueField`/`SettingsSecretField` 做字段、
  `SettingsFormModel` 管暂存。自绘开关/输入框是明确的反模式——库里有就必须用，否则下次主题层
  调圆角标度时你的卡片会独自漂移（`vlln/whale-girl` 的实体教训，其决策记录
  `2026-10-04-settings-card-official-controls` 记了全过程）。
- **卡片材质照抄三行**（`docs/ui-radius.md` 的"Settings card materials"）：

  ```css
  .card {
    border-radius: var(--dsw-radius-xl);              /* R20 */
    border: 0.5px solid var(--dsw-alias-settings-card-stroke);
    background: var(--dsw-alias-settings-card-fill);
  }
  ```

- **字段行分隔线只在相邻字段之间**：官方是"相邻 `.field` 之间 `border-top: 0.5px`"——
  中间插一层普通 `div` 线就没了。
- **保存语义先想清楚**：`SettingsForm` 只在点保存时写、**离开页面即丢弃草稿**（没有取消按钮）；
  要"改完立即写入"就别用它（用 `SettingsFormModel` 自己 save，或直接写 scope）。
- 库内确实没有的语义才自绘，并在文件头注释写明理由（示例：多行文案池——官方没有
  "Enter 换行、Shift+Enter 提交"这类多行编辑语义的控件）。
- 槽位注册写法见 [07-settings-panel.md](07-settings-panel.md)（`plugins.item` / `plugins.bundle.config` …）。

### 10.2 会话页签 / 全局面板页

- 挂 `conversation.view`：**给视图根元素加稳定 `data-*`**（如 `data-mypanel-view`），并
  `:has([data-mypanel-view]) [data-width-handle]{display:none}` 关掉随之继承的拖动宽度手柄
  （见 [13-gotchas.md](13-gotchas.md) 12）。不要锚官方 CSS Module 的哈希类名。
- 挂 `main` 全局面板：入口页顶部自 pad `--dsh-frame-top-clearance`（Windows 是 caption 高度）；
  内容贴到左上角时再 pad `--dsh-frame-leading-clearance`。同一 `id` 也要在 `sidebar.panellist` 注册图标。
- 面板底色用 `--dsw-alias-bg-base` / `-layer-1`；不要自带整页背景、自带滚动条皮肤或 `z-index` 军备竞赛。

### 10.3 侧栏条目

- 行几何照抄：`min-height: 36px; padding: 7px 8px; border-radius: var(--dsw-radius-md); gap: 8px`；
  图标尺寸展开 16 / 折叠 18；hover / active 用
  `--dsw-specific-sidebar-nav-item-hover` / `--dsw-specific-sidebar-nav-item-active`。
- 面板图标要接受 `{ size, active }`（折叠态会以 18 渲染）。

### 10.4 composer 条上的动作

- `conversation.input.activity` **只放一个动作**（模型选择器与 Send 之间）；用
  `Button variant="ghost" size="sm"`（H28/R8）或 24–28px 图标按钮 + `Tooltip`。
- 展开面板要自己回收工具栏的展开态（卸载时撤销）。

### 10.5 反馈与提示

- 瞬态提示用 `Toast`（顶部居中、`z-index: 1100`）；行内状态用 `StateDot` / `ConnectionIndicator`；
  不要另造第三个位置的横幅。
- 危险操作走 `RiskConfirmation`（勾选门禁 + `Modal` 的键盘/焦点契约）。

### 10.6 工具输出的自定义卡片

- 先按 §8.0 选型表挑官方卡片（`TerminalBlock` / `ReadBlock` / `DiffBlock` / `SearchBlock` / `WebBlock` /
  `JsonTree` / `MarkdownText` / `CodeBlock`）；能套就套。
- 要在卡片上加重试/导出之类的东西，**包在卡片外层**（或在官方给出的 `labels`/`toolbarLabels` 里加），
  不要去改卡片内部结构或覆盖它的 `--dsl-*` 几何变量之外的样式。

### 10.7 给命令（`/` 菜单）加图标与本地化标题

`/` 菜单一行能显示的字段不止图标。先认清谁给什么——**宿主命令描述符只有
`description`（和 `input.hint`），`label` / `icon` 都在客户端**：

| 字段 | 谁给 | 说明 |
|---|---|---|
| `name` | 命令名 | 标题兜底；`label` 与 name 不同（忽略大小写）时，菜单在标题后显示灰色 name 别名 |
| `label` | 客户端 | 行标题；缺失时菜单按 `label ?? name` 回退成裸命令名。它也是 `/` 菜单的第二个搜索键，但**前提是候选在搜索前就带 label**；宿主命令的输出贴面做不到（见 B） |
| `description` | 宿主 descriptor / 客户端贡献 | 副标题。宿主命令的描述由 Node half 提供；若插件已做语言回传（§08-i18n），通常不必在客户端再抄一份 |
| `icon` | 客户端 | 14px；给 `@deepseek-ai/dsh-client-ui-primitives` 的 `Icon*` 组件 |
| `hint` | 宿主 `input.hint` | **claim 态的 ghost text，不在菜单行渲染**；别把它当菜单说明 |
| `section` | `sectionRows` | 宿主行由 ui-commands 统一加「指令」；自己写会被覆盖 |

按命令的**来源**分两种情况：

| 你的命令是 | 能否加 label/icon | 做法 |
|---|---|---|
| **客户端自有命令**（`ctx.commandUi.register`） | ✅ 官方支持 | 贡献里带 `label` / `description` / `icon`（见 A） |
| **宿主命令**（`ctx.commands.register`，有带参形式与生命周期记账） | ❌ 没有官方入口 | 见 B 的两条路 |

**A. 客户端自有命令（首选）**——行为全在浏览器里时，直接注册带 `label`/`icon` 的贡献。`t` 用 `ctx.locale.bind(NS)`，`label()` / `description()` 每次候选合成都会重新调用：

```ts
ctx.inject(['commandUi'], (scope) => {
  scope.effect(() => scope.get('commandUi').register({
    name: 'mycmd',
    label: () => t('cmd.label'),                   // 每次候选合成现取，切语言即生效
    description: () => t('cmd.description'),
    icon: IconRefreshOutlineRegular,               // ui-primitives 的图标组件
    available: session => true,
    ui: { kind: 'action', run: (session) => { /* … */ } },
  }), 'my-plugin: command')
})
```

- 图标给 `@deepseek-ai/dsh-client-ui-primitives` 的 `Icon*` 组件即可；菜单以 **14px** 渲染。
- ⚠️ **名字不得与任何宿主命令重名**：候选合成阶段会抛
  `ui-commands: contribution /x collides with a host command`，**整组「指令」一起消失**（不是只丢这一行）。
- 参考实现：官方 `ui-model-selection` 的 `/model`（`popupSelect` + `IconDataOutlineRegular`）。

**带参命令的三种处理**：

- **宿主命令**：`input: { hint }` 只给 composer claim 态的 ghost text；参数由 `handler(invocation.rawInput)` 解析，菜单行不显示用法（要展示就写进 `description`）。
- **客户端贡献**（`commandUi.register`）：只处理**裸调用**；`/mycmd 5m ...` 这种带参行会落回默认 sink，除非另注册 source。
- **客户端源**（`inputTriggers.registerSource`）：在 `matchEnter` 里自己解析整行；返回 `'handled'` 时还要自己消费 token（`slash/input-consume-token`）。`onPick` 可返回 `{ text: '/mycmd ' }` 让用户接着输入，或用 `matchClaim` 恢复历史 chip。参考 `dsh-context` 的 `/context`。

**B. 宿主命令：0.2.0-rc.2 / 0.2.1 没有官方行外观入口**——先认清三条事实，别去试错：

- 行外观是 `ui-commands` 里一张**硬编码的一等公民表**（`HOST_FACES`：goal / plan / feedback /
  compact / permission / export），按 `definitionId` 命中；第三方命令命中不了。
- 同名客户端贡献 → 上面那条 fail loud；`decorate` 也不行，它只替换**裸调用**的行为
  （带参的命令行仍走宿主处理器），且契约里**没有 `label` / `icon`**。

于是只剩两条路：

1. **接受官方回退外观**（行上只有 name + 宿主 description，无图标、无本地化标题）——零风险。
2. **贴面**：在候选合成出口 `commandUi.candidates(session, req)` 上包一层，**只重写自己那一行**的
   `label` / `icon`（`description` 通常已由宿主给；要改也可以，但别把同一句话维护两份）；
   前提不成立（服务缺席、上游改名、导出非函数）就静默降级：

```ts
interface Row { readonly name?: string; readonly label?: string; readonly icon?: unknown }
type RowLabel = (key: 'cmd.label') => string

function installRowFace(commandUi: unknown, t: RowLabel): () => void {
  const runtime = commandUi as { candidates?: (s: unknown, r: unknown) => Promise<readonly Row[]> }
  const original = runtime?.candidates
  if (runtime === undefined || typeof original !== 'function') return () => {}
  const face = async (s: unknown, r: unknown): Promise<readonly Row[]> =>
    (await original.call(runtime, s, r))
      .map(row => (row?.name === 'mycmd'
        ? { ...row, label: t('cmd.label'), icon: IconRefreshOutlineRegular }
        : row))
  runtime.candidates = face
  return () => { if (runtime.candidates === face) runtime.candidates = original }
}

const t = ctx.locale.bind(NS) // NS = 你的 locale 命名空间；调用时读当前 active，切语言后下一次候选合成即生效
ctx.inject(['commandUi'], (scope) => {
  scope.effect(() => installRowFace(scope.get('commandUi'), t), 'my-plugin: command row face')
})
```

   这是**登记在案的越界**（`candidates` 不是公开契约，它是 `/` 源的候选合成出口）。可接受的理由与
   必须守住的边界：不碰命令目录、不碰派发、不碰命令生命周期，不新增命令、不写 DOM、不引 timer，
   只改自己那一行的展示字段；`ctx.inject` 让没有命令目录的 composition 里这段代码**永不执行**；
   上游改名后包装不生效，该行自动回落成官方外观，**功能不受影响**。
   参考实现：`vlln/dsh-loop` 的 `installCommandRowFace`（宿主命令 `/loop` 保留带参形式与生命周期，
   只贴一行的本地化标题与图标），以及同做法的社区插件 `falling-ts/dsh-force-compact`。

**贴面只能修显示，不能修搜索**：`rankByName` 在 `candidates` 内部、贴面之前运行；输出贴面加上的 `label` 不参与这次查询。空查询或命中 name 的查询会显示 label；`/循环` 这类只命中 label 的查询仍为空。要让本地化标题可搜，只能用客户端自有贡献/源。

**验证（两条路都要过）**：`/` 菜单里那一行出现图标 + 本地化标题；标题与 name 不同时出现灰色别名；
切界面语言后标题跟着变；官方行（`/goal`、`/compact`…）与其他插件的行一字未变；没有 `commandUi` 的
composition（或上游改名）时不报错、只是回落到 name + description。**客户端自有命令/源**再验「用本地化
标题能搜到」；**宿主命令的输出贴面只修显示**，`/循环` 仍不命中（搜索在贴面之前）。

## 11. 交付前视觉自检

> 来源：`docs/ui-radius.md`「Apply and verify」（分类角色、对齐填充、浅深两主题实看、用现有门禁）
> 与 `docs/web-styling.md` 的组件规则——本清单是它们的插件版。

1. **浅色 + 深色各看一次**（切换宿主主题）——确认没有写死的颜色漏出来。
2. **状态过全**：静止 / hover / active / 选中 / disabled / 键盘 `:focus-visible`（用 Tab 走一遍，
   别用鼠标点）。
3. **几何配对**：圆角按 §3 的角色表选；胶囊 `999px` 与圆 `50%` 都配了 `corner-shape: round`；
   固定外高用了 `box-sizing: border-box`。
4. **层级正确**：抬升面 `border: 0` + `--dsw-elevation-*`；中性边框/分隔线 0.5px；
   菜单没覆盖主题材质；浮层 z-index 与 §8.2 表一致（别超过 Toast 的 1100）。
5. **动效负责**：自绘动画有 `prefers-reduced-motion: reduce` 分支。
6. **文案负责**：所有面向用户的话都由你传入（官方控件没有语言兜底，缺参会类型报错）。
7. **没有抄第二份**：能用官方控件的都用了；自绘处注释写明"库内没有该语义"的理由。
8. **窄布局不破**：长标签、长路径、长文案、长 JSON 不撑破容器（`min-width: 0`、`overflow-wrap`、
   横向滚动交给既有滚动区）。
9. **样式没被宿主吃掉**：关键样式按 [13-gotchas.md](13-gotchas.md) 4 用内联兜底；
   在真实 GUI 里确认过渲染结果，而不是只看源码。

## 未确认与已知源码边界（0.2.0-rc.2）

> 来源：本次核查（tag `dsh-v0.2.0-rc.2`）的留白与源码边界；逐条在正文对应处已标出。

- **本文件数值来自 `dsh-v0.2.0-rc.2` 源码。** master 已有新增（`InlineEditor`、`HoverCardGroup`、
  `CommandText`、字体设置行等），**安装版上不存在**；写代码前先在你的应用 bundle 里核实符号存在
  （[13-gotchas.md](13-gotchas.md) 10）。
- **两个悬空 token**：`ui-primitives` 的 `settings-form/SettingsForm.module.css` 读
  `--dsw-alias-label-error`、`settings-form/fields.module.css` 读 `--dsw-alias-bg-layer-4`，
  而 `ui-theme` 的 8 张样式表（含 master）**都没有定义**这两个名字。自绘时不要照抄。
- **未从包入口导出**（`package.json#exports` 只有 `"."` 一个入口）：`ConfigField`、`CodeToolbar` 组件
  （只有 `CodeToolbarLabels` 类型）、`ImagePreview`、`TooltipSuppression`。
  复用代码 header 的唯一公开途径是 `CodeBlock.toolbarLabels` 或直接用 `ReadBlock`/`DiffBlock`。
- `HoverCard` 的 `compact` 卡片背景是模块内硬编码字面量 `--dsw-hovercard-bg`（不是主题 token）；
  要跟随主题变色请选 `preview` / `inline`。
- `Menu` 的 `side: 'right'` 只对 `portal` 模式生效（原地模式 CSS 只实现了 sideTop/alignEnd）。
- 浮层（`Modal` / `HoverCard` / `Toast` / `ImageLightbox` / `RiskConfirmation`）**都不做 body 滚动锁**；
  需要时自己加。
- `CodeCard.tsx` **不存在**，只有 `CodeCard.module.css`（read/diff 卡片与代码 header 的共享样式表，
  非公开 API）。
- 未核到的槽位元数据：`sidebar.*` / `settings.*` / `plugins.*` 的多数 key 的 cardinality/scope——
  快照内只有 `main`（keyed+root）、`shell.leading`（single+root）、`sidebar.panellist`（list+root）、
  `settings.plugins.tab`（list+root）四处可证；其余按官方 `docs/subsystems/slots.md` 与
  [07-settings-panel.md](07-settings-panel.md) 现场核实。
- `PathLabel` 依赖的 `pathPartsOf`（`@deepseek-ai/dsh-util-workspace-path`）目录/文件名切分语义
  未在本次核查范围内确认。
