<!--
README 模板（发布前删除本段注释）

用法：
1. 先决定要哪些块：hero 图 / 多语言 / 徽章 / 截图 / 逐面详解 / 安全 / 宿主矩阵 /
   卸载 / AI 助手安装块。用不上的整块删掉，不要留空标题。
2. 把所有 {…} 换成真实内容，发布前全文搜一遍 `{`。
3. 安装命令必须能直接复制执行；零依赖包只给 git 源。
4. 生效条件（重启 / 刷新 / 无需）按目标环境实测写，不默认加。
5. 全文目标 ≤ 200 行；工程备忘录放 AGENTS.local.md 或 docs/engineering-notes.md。
6. 双语：另建 README.zh.md / README.en.md，顶部互链。
7. Desktop 与 web 的差异见 references/14-desktop.md（安装走应用内插件页）。
8. 社区徽章只在**真的被收录**后才放；放了就要能点进去看到自己。
-->

<!-- 可选：社媒预览图 / hero，放在标题上方 -->
![{插件名}](docs/social-preview.png)

<h1 align="center">{插件名}</h1>

<!-- 可选：语言切换 -->
[English](README.md) | [中文](README.zh.md)

<!-- 核心徽章：至少留 dsh 版本 -->
[![npm](https://img.shields.io/npm/v/{package})](https://www.npmjs.com/package/{package})
[![stars](https://img.shields.io/github/stars/{owner}/{repo}?style=flat)](https://github.com/{owner}/{repo})
[![dsh](https://img.shields.io/badge/dsh-{0.2.0--rc.2}-blue)](https://www.deepseek.com/harness/)

<!-- 可选：dsh 生态收录徽章（被收录后再放，二选一或都放） -->
[![awesome-dsh-plugin](https://awesome-dsh-plugin.com/badge.svg)](https://awesome-dsh-plugin.com)
[![listed on dsh-plugin.org](https://dsh-plugin.org/badges/listed.svg)](https://dsh-plugin.org/plugins/{owner}/{repo})
[![dshfind](https://dshfind.com/api/badge/{owner}/{repo})](https://dshfind.com/en/plugins/{owner}/{repo})

**{一句话价值主张：它是什么 + 用户拿到什么好处}。**

<!-- 可选：真实的社会证明，没有就别写 -->
> 被 {谁} 推荐 / 在 {场景} 里被使用——链接。

## 30 秒安装

<!-- 有 GUI 入口先写 GUI（大多数用户走这条） -->
**在 dsh web / Desktop 里**：打开 **Plugins → 添加插件**，输入 `{package}`，点安装。

**用 CLI**：

```sh
# web（官方 dsh web）
dsh plugin --profile web add {package}

# 官方 Desktop：先用应用内 Plugins 页；或用 Desktop 自带的 dsh 命令（先完全退出应用）
dsh plugin --profile desktop add {package}

# 升级
dsh plugin --profile web update {package}@latest
```

- **生效条件**：{装完刷新页面即可 / 需要重启宿主 / 无需重启——实测写}
- **前置**：dsh `{≥ 0.2.0-rc.2}`；{其它依赖}
- **装不上时**：{最常见原因 + 用户可见症状}
- **卸载**：`dsh plugin --profile web remove {package}`（{若有 `/xxx uninstall` 之类命令，写在这里}）

### 装好之后怎么确认

- {界面上应出现什么：页签 / 侧栏条目 / 命令}
- {跑一条只读检查：`/{cmd} status` 或打开某面板}
- {装完还需要做什么：到哪个页面点 Apply / 重启一次——没有就删掉}

<!-- 可选：给 AI 助手的安装块（很多用户会让 coding agent 代装） -->
<details>
<summary>给 AI 助手的安装提示（复制即用）</summary>

安装 DeepSeek Harness 插件 `{package}` 到 `{profile}`。只运行安装命令：不要扫描磁盘、
不要读改其它文件、不要改配置、不要重启宿主。若 `dsh` 不在 PATH 上，告诉用户后停止。

```sh
dsh plugin --profile {profile} add {package}
```

装完告诉用户下一步：{重启宿主 / 在 Plugins 页启用}。

</details>

## 为什么需要它

{用户视角的痛：现在必须怎么做、代价是什么，这个插件把哪一步交给了工具。}

{与相邻方案的区别：官方自带 / 同类插件，谁发起、用户要做什么、差别在哪。}

## 用起来是什么样

![{主界面}](docs/overview.png)

### {面 1：页面 / 页签 / 命令}

{用户视角：打开哪、看到什么、做什么。}

| 区域 | 它回答什么问题 |
|---|---|
| {卡片 / 区块} | {用户的问题} |
| {卡片 / 区块} | {用户的问题} |

### {面 2：…}

{同上；每个"面"一节，配一张图和一个问题表。多状态分开截图，不拼图。}

## 能力面

| 工具 | 说明 |
|---|---|
| `{tool_name}` | {用户能看懂的一句话} |

| Skill | 作用 |
|---|---|
| `{skill-name}` | {一句话} |

| MCP | 说明 |
|---|---|
| `{server}` | {暴露什么；需要什么凭据} |

## 配置

| 项 | 默认 | 说明 |
|---|---|---|
| `{key}` | `{default}` | {用户能理解的一句话} |

环境变量：`{VAR}` — {作用与取值范围}。

{在哪改：Plugins 页 → 本插件 → 配置卡片；改完是否即时生效。没有配置就删掉本节。}

## 安全与数据

- {需要什么权限 / 访问哪些路径 / 会不会执行命令}
- {会不会外发数据：发到哪、发什么、能不能关}
- {凭据放哪：环境变量 / 系统凭据 / 从不存}

{没有网络、执行、文件写入的插件可以只留一句"仅在本地读写，不外发"。}

## 支持的宿主与版本

| 宿主 | profile | 状态 |
|---|---|---|
| 官方 `dsh web` | `web` | ✅ 已验证（dsh {0.2.x}） |
| 官方 Desktop | `desktop` | ✅ / ⚠️ 未验证——说明差异 |
| 其它 profile / 第三方 Desktop | — | ⚠️ 未验证 |

| dsh 版本 | 用哪个插件版本 |
|---|---|
| `{0.2.x}` | `{1.x}` |
| `{0.1.7}` | `{0.x}`（旧 tag） |

web 与 desktop **安装互不相通**，两个宿主各装一次。

## 已知限制

- {用户会撞上的边界：平台、并发、不处理的场景}
- {与官方能力的边界：它不替代什么}

## 插件管理

装/卸/启停用官方 CLI：`dsh plugin --profile web add|remove <包>`；已装插件在**侧边栏 Plugins 页**
里查看与配置——每个插件自己的配置页挂在那个包页上（Settings 里的「插件」只是只读清单，改不了配置）。
Desktop 上从应用内的 Plugins 页安装与管理。

## 兼容性

{与 package.json 的 peer 范围同源；README 下限不能高于 peer 下限。Desktop 的版本跟应用走。}

| dsh 版本 | 状态 |
|---|---|
| `{0.2.0-rc.2}` | ✅ 已验证（{2026-10-18}） |
| 其它版本 | ⚠️ 未验证——升级后若 {症状}，多半是 {原因} |

## 反馈与贡献（可选）

- Bug / 想法：{issues 链接}；{有没有 roadmap / discussion}
- 喜欢的话给个 ⭐：{repo 链接}

## 许可

{MIT}。{第三方素材 / 图标来源与许可，如果有。}
