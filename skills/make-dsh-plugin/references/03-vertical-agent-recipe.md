# 从零搭一个垂直 Agent（视频 / 抓包 / 任意领域）

> **本文件回答**：从零搭垂直 Agent 的顺序、每步检查点、常见返工。**不回答**：字段级契约（→ 02 / 04）、UI 规格（→ 06）。

**来源**：概念依据见 [01-concepts.md](01-concepts.md)；文件与命令细节分别落在 [02-profile-and-preset.md](02-profile-and-preset.md)、[04-plugin-contract.md](04-plugin-contract.md)、[05-bundle-plugins.md](05-bundle-plugins.md)、[06-ui-style.md](06-ui-style.md)、[10-install-and-verify.md](10-install-and-verify.md)。本页是把它们串成一条端到端路径，不重复契约。

## 目标形态

做一个"视频制作 Agent"，交付的不是一个工具，而是一个**能启动的产品**：

| 产物 | 单位 | 用户看到什么 |
|---|---|---|
| 领域工具（配音、生图、字幕、检索…） | 若干 plugin，聚成一个 bundle | 模型能调用的工具 |
| 该领域的做事方式 | 一个 agent preset | 新任务里的「视频模式」 |
| 预览 / 播放 / 时间线 | client half + 新 profile | 侧边栏里的一套界面 |
| 启动方式 | profile（例如 `video`） | `dsh --profile video` |

三步走：**工具 → preset → UI + profile**。顺序重要：先让模型能用工具，再让它按你的流程用，最后才做界面。

> **先原型、后产品**：只给本机用或还没想清楚形态时，可以先用产品内的**创造模式**（`cordis` preset）把 bundle 写出来、装进当前 profile 试；确认要分发再按本页仓库化（交接清单见 [05-bundle-plugins.md](05-bundle-plugins.md)「创造模式」）。

## 第 1 步：领域工具（plugin + bundle）

每个工具是一个普通 Cordis 插件（[04-plugin-contract.md](04-plugin-contract.md)），用 `defineTool` 注册；同领域的工具用一个 bundle 聚合（`dsh.bundle.patch` 可为数组，也可一个 patch 里多行 insert）。

```jsonc
// video-tools/package.json
{ "name": "dsh-video-tools", "version": "0.1.0", "type": "module",
  "main": "./index.mjs",
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } } }
```

```yaml
# video-tools/cordis.patch.yml
- insert:
    - id: video-tts
      name: 'dsh-video-tools'        # 同包多工具：用不同 id + 配置区分，或拆多个包
      config: { feature: tts }
    - id: video-image
      name: 'dsh-video-tools'
      config: { feature: image }
```

**放 Host 还是 preset？** 默认 **Host 行**（所有模式都能用）；只有"要按模式裁剪"时才进 preset 行。判据见 [01-concepts.md](01-concepts.md) L2。

**检查点**：真启动 profile + **真调用一次工具**；工具 description（模型可见，不翻译）写清"什么时候该用它"。

## 第 2 步：preset（人设 + 流程 + 工具）

新增一个模式，只需要一个声明行（完整字段与覆盖语义见 [02-profile-and-preset.md](02-profile-and-preset.md) §2）：

```yaml
- insert:
    - id: preset-video
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: video
        name: 视频制作
        description: 写脚本、配音、生图、出字幕并拼成片。
        order: 10
        plugins:
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config:
              prefix: |
                You are a video production agent. Follow the pipeline:
                script → voice-over → visuals → subtitles → assemble → preview.
                Ask for the brief first; never invent brand assets.
          - id: agent-instructions
            name: '@deepseek-ai/dsh-agent-instructions'
          - id: tool-video-tts           # 只在视频模式里出现的工具
            name: 'dsh-video-tools'
            config: { feature: tts }
          - id: tool-video-preview
            name: 'dsh-video-tools'
            config: { feature: preview }
```

**不要在这里找模型配置**：模型路由是宿主设置（`agent-default-model` / 设置页），preset 没有模型行。不同模式要不同模型，用部署配置或设置，不要发明 preset 字段。

**检查点**：新开一个会话，选「视频制作」，确认工具目录里**只**出现视频工具 + 通用工具；再跑一遍老模式，确认没被影响。

## 第 3 步：专属 UI + 新 profile

- **UI**：client half（`dsh.client`）+ 槽位注册；先读 [06-ui-style.md](06-ui-style.md)，用官方控件与 token，不要写死颜色、不要自造第二套控件。会话页签注意 `conversation.view` 的宽度手柄坑（[13-gotchas.md](13-gotchas.md) 12）。
- **profile**：`video` 是一个新 profile，不是新代码路径。

```sh
# 首次：用随附 web 模板复制一个自定义 profile，然后加自己的 bundle
dsh --profile video --from-default-profile web
dsh plugin --profile video add ./video-tools        # 本地自测；发布后用 git 源

# 启动（安装版）
dsh --profile video
# 源码 checkout
pnpm dsh --profile video
```

**检查点**：profile 的 `package.json#dsh.profile.bundles` 里能看到自己的包；`dsh --profile video --dump-config | grep preset-video` 有行；新会话里能看到「视频制作」。

> Desktop 上不新建/切换 profile：插件与应用都挂在 Electron 独占的 `desktop` profile 下，安装走应用内 Plugins 页（见 [14-desktop.md](14-desktop.md)）。

## 能力 → 层 → 文件 对照

| 你要加的东西 | 放哪 | 典型文件 |
|---|---|---|
| 工具、服务、命令、宿主 UI | Host 行 | bundle 的 `cordis.patch.yml` |
| 只在某模式出现的工具 / 人设 / 技能 | preset 行 | 同上，`preset-<id>` 的 `config.plugins` |
| 新的「模式」 | preset 声明行 | 独立 bundle 或并入工具箱 bundle |
| 新的启动方式 | profile | `$DSH_HOME/profiles/<name>/package.json` |
| 纯提示词资产 | skill 包 | `skills/<name>/SKILL.md` |

## 常见返工点

1. **把"要按模式变化"的工具做成 Host 行** → 只能全局开关，最后只能推翻重做成 preset 行。
2. **在 preset 里找模型 / 会话语义** → 找不到；这类东西在宿主设置。
3. **UI 写死颜色或自造控件** → 深浅色切换即破相；返工成本比一开始读 [06-ui-style.md](06-ui-style.md) 高。
4. **没把包装进 profile 树** → 官方包解析不到，整棵 profile 起不来（不是"插件不可用"）。
5. **改完 preset 用老会话验证** → 老会话保留旧代际，看起来像"没生效"；必须新开会话。

## 复用：换成抓包分析

同一套骨架只换三样东西：**工具集合**（bundle 换包）、**preset 的 persona 与工具行**（流程换文本）、**UI**（预览换成流量时间线）。profile 名换掉即可并存——两个垂直产品共享同一个 dsh 安装与宿主能力。
