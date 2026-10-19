# dsh 的概念地图（先读这一篇）

> **本文件回答**：dsh 为什么这么分层（五种单位 / 两棵树 / 生命周期 / 术语）。**不回答**：命令、字段、层栈细节（→ 02）、怎么搭产品（→ 03）。

**来源**：官方 `apps/cli/reference/README.md`（profile / 层栈 / 插件管理）、`packages/boot/app-boot/README.md`（profile 与模板）、`packages/preset/*/README.md`（agent preset）、`packages/bundle/*/cordis.patch.yml`（宿主行与 preset 行的实证）、`packages/core/agent-tool-presentation/README.md`（host/preset 边界的官方论证）、`docs/subsystems/permission-presets.md`。实测基线见 [02-profile-and-preset.md](02-profile-and-preset.md) 开头。

**这一篇只回答「为什么这么分层」。** 要抄配置、查命令、看字段，去 [02-profile-and-preset.md](02-profile-and-preset.md)。

## L0 一句话

dsh = **Cordis 运行时** + 一套内置能力（工具、会话、设置、Web GUI）。**一切能力都是插件**：插件在 `apply(ctx)` 里声明自己提供的服务与 `inject` 依赖，Cordis 负责注入、排序与生命周期（load / update / dispose）。没有"内核特权层"——官方能力也是同一批 npm 包，只是随 dsh 安装一起分发。

## L1 五种装配单位

| 你会听到 | 单位 | 是什么 | 落点 | 谁消费 |
|---|---|---|---|---|
| 运行方式（web / headless） | **profile** | 一份装配 + 一套依赖 | `$DSH_HOME/profiles/<name>/` | 启动器 `dsh --profile <name>` |
| 插件包 / 一组插件 | **bundle** | 一个声明了 `dsh.bundle.patch` 的 npm 包 | `package.json#dsh.bundle` | profile 的 `dsh.profile.bundles` 列表 |
| 插件 / 组件 | **plugin** | 一个 Cordis 插件（`name`/`inject`/`apply`） | npm 包 + entry | Loader 按 patch 行挂载 |
| 模式（标准 / 极简 / 创造） | **agent preset** | 一个 Agent 的子插件列表 | `preset-<id>` 行 | 会话创建时选一个 |
| 技能 | **skill 包** | 无代码的 `SKILL.md` 目录 | `.dsh/skills`、`.agents/skills`、`$DSH_HOME/skills` 等发现根 | agent 的 skill 工具 |

**"插件可以是 bundle"的准确说法**：bundle 是**分发/组合单位**，plugin 是**功能单位**。一个 npm 包可以：

- 只是 plugin（没有 `dsh.bundle`，装完在 profile patch 写一行 insert）；
- 只是 bundle（只分发别人的插件行，甚至只分发 preset 声明）；
- 同时是两者（有 `main`，patch 里 insert 自己）；
- 是 bundle 且 `patch` 为**数组**——一个包分发多份 patch（官方 web-app 就用它同时带宿主行与 4 个 preset）。

## L2 两棵树

```
$DSH_HOME/profiles/web/          ← profile：装配 + 安装/解析边界
  package.json                   dsh.profile.bundles: [base, web-app, …]
  cordis.patch.yml               ← 用户层
  node_modules/                  ← 装进来的 bundle
        │
        ▼ 启动：bundles 依序 → profile patch → home patch → --patch
┌────────────────────── 宿主树（一个进程一棵） ──────────────────────┐
│ llm / agent-default-model / agent-loop / session / settings        │
│ sandbox / approval / tools 注册表 / webServer / client modules     │
│                                        —— 所有 Agent 共享 ——       │
│                                                                    │
│  preset-standard   preset-ptc   preset-minimal   preset-cordis     │
└────────────────────────────────────────────────────────────────────┘
        │ 新会话选中某个 preset
        ▼
  Agent 树（每会话一棵，独立 scope / Loader 子树）
  persona / agent-instructions / tool-bash / tool-fs / skill / compaction …
```

- **宿主行**：模型路由、Agent 循环、会话与持久化、设置、沙箱与审批、**工具注册表本体**、HTTP/UI。
- **preset 行**：该 Agent 的**工具行**、人设、提示词段、技能、计划/压缩策略。
- **放置判据是消费者在哪**：服务的消费者全在宿主平面时，它只能留在宿主。官方 `agent-tool-presentation` 把这点讲得最清楚——工具注册表搬不进 preset，**preset 能拥有的是「呈现方式」**，所以 PTC 与 native 能在同一进程并存。

## L3 生命周期与边界

| 改了什么 | 怎么生效 |
|---|---|
| `dsh.profile.bundles` 列表（装 / 卸 / 升级 bundle） | **重启 profile** |
| profile 或 home 的 `cordis.patch.yml` | 启用 HMR 时热应用；否则重启 |
| preset 声明（`config.plugins` / 元数据） | 之后**新建**的 Agent 用新代际；已有会话保留旧代际 |
| 会话选 preset | 只有**空白会话**能换；首个 turn 开始后锁死（`agent-preset/locked`） |
| 恢复会话 | 按记录的 preset id 找**当前**定义；定义不存在 ⇒ 拒绝恢复 |
| 装到 profile 树外 | 官方包解析不到 ⇒ **整棵 profile 起不来** |

## L4 术语对照

| 用户说法 | 实际单位 | 备注 |
|---|---|---|
| web / headless / 运行方式 | profile | 名字自取；随附模板只有 5 个 |
| 标准 / 极简 / PTC / 创造模式 | agent preset | GUI 叫「模式」，设置页叫「Agent 预设界面」 |
| 插件 / 组件 | plugin | 可以有 Node half 与 client half |
| 插件包 / 一个包带一堆插件 | bundle | `patch` 可为数组 |
| 技能 / SKILL.md | skill 包 | 不进 profile 装配 |
| 权限 / 自动批准 | **permission preset** | 沙箱 + 审批的命名组合，与 Agent 能力无关 |
| 扩展 / extensions | 另一子系统 | Agent 写版本化 Cordis 包并运行，两半；不是 preset |
| Desktop / 桌面版 | Electron 宿主 | 同一套 Web 应用 + 自己的 `desktop` profile（→ 14） |
| 创造模式 / Creator | `cordis` agent preset | 产品内写 bundle 并 `install_bundle`；与仓库路径的分工见 [05](05-bundle-plugins.md)「创造模式」 |

## 四个最容易教错的点

1. **「preset 里有大模型和 Agent 循环」——错。** 模型（`llm`、`agent-default-model`）与循环（`agent-loop`）、会话、沙箱都在宿主树；四个随附 preset 的 patch 里没有任何模型行。preset 改的是这个 Agent 的**工具 / 人设 / 技能**。
2. **「bundle 是插件的一种」——不准确。** bundle 是分发与组合单位，可以只分发别人的行；plugin 才是功能单位。两者可合体，但不是包含关系。
3. **「profile 只是把 bundle 拼起来」——漏了最要命的一半。** 它同时是**安装与模块解析边界**：依赖装在它里面、`node_modules` 在它里面、runtime resolution 按它计算。所以"装到树外"不是找不到包这么简单，是整棵起不来。
4. **「模式 = 权限预设」——两套东西。** 模式（agent preset）决定工具与提示词；权限预设决定沙箱模式 + 审批策略。

## 垂直 Agent 三步法（一句话版）

**工具插件 → preset（人设 / 流程 / 工具）→ 专属 UI + 新 profile**，然后 `dsh --profile <name>`。
换一套工具与提示词就能复用到别的领域。展开见 [03-vertical-agent-recipe.md](03-vertical-agent-recipe.md)。
