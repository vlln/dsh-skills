# 生态与渠道

> **本文件回答**：发布到哪、市场是什么、社区在哪、生态里有什么可参考。
> **不回答**：发布纪律与交付清单（→ [11-publish.md](11-publish.md)）、安装与验证机制（→ [10-install-and-verify.md](10-install-and-verify.md)）、打包渠道细节（→ [05-bundle-plugins.md](05-bundle-plugins.md)）。

**来源**：官方 `README.md`「社区与支持」、`docs/user/guide/plugin-market.md`、`packages/boot/plugin-market`、`packages/util/plugin-market-index`、`apps/plugin-market-generator`；社区与市场条目来自公开网络，会变化——以入口现状为准。

## A 渠道总览

| 渠道 | 托管什么 | 谁维护 | 什么时候用 |
|---|---|---|---|
| npm / git / tarball / prepare 构建 | **包本身** | 你 | 分发代码（四条渠道见 [05-bundle-plugins.md](05-bundle-plugins.md) 与 SKILL.md Step 5） |
| **市场索引（JSON）** | **元数据 + 版本列表**，不托管包 | 任何索引维护者 | 被「发现」页搜索、一键安装 |

⚠️ 市场不是第五条包渠道：索引只列出 npm / git 来源与版本，安装仍走普通 `dsh plugin` 通道并再做一次兼容性检查。

## B 插件市场（机制）

- **本质**：一个 UTF-8 JSON 索引文件（`format: 1`），列出 bundle 的标题、图标、作者与版本。**DSH 不内置任何索引源**——用户自己添加。
- **用户侧**：Plugins → **实验性插件** → 打开「**自定义插件市场**」（可选 bundle `@deepseek-ai/dsh-experimental-plugin-market-bundle`）→「**发现**」页 → **添加索引源**（填索引 URL）。打开后 Creator 模式也会获得只读的 `plugin_market` 工具；关闭该 bundle 即移除这两者。
- **索引源是 per-profile 的**：每个 profile 各自维护 URL 列表，切换 profile 不会共享。
- **URL 要求**：`http:` 或 `https:`，不能含用户名/密码/`#` 片段。`http:` 索引的**任何网络中间人都能改**其中列出的安装 spec——不受你控制的网络必须用 `https:`。
- **发布索引（发布者侧）**：
  1. 写来源清单（每行一个 npm 包名或 https Git 仓库 URL）：
     ```sh
     pnpm --filter @deepseek-ai/dsh-plugin-market-generator start \
       --input plugins.txt --output site/index.json --title "Team plugins"
     ```
  2. 静态托管：2xx、**无重定向**、默认 ≤ 128 MiB、UTF-8；图标内联（base64）或单独文件（跨源**必须 https**，相对路径相对索引 URL 解析）。
  3. 把 `index.json` 的 URL 给用户，让他在「发现」里添加。
- **索引语义**：每个版本带 `source`（npm / git）与 `engines.dsh`；安装时 DSH 会**再校验一次**兼容性。Git 版本装成 `git+<url>.git#<commit>`（子目录追加 `&path:/<path>`），npm 版本装成 `name@version`（有 `registry` 时先问它）。
- **信任边界**：市场是第三方内容；DSH 只校验**文件格式**，不验证标题/图标/来源声明。只添加可信索引源，安装前核对确认框里的来源。
- **发布前自检**：`packages/util/plugin-market-index` 是官方索引校验器库，可在流水线里跑格式检查。

## C 社区

| 渠道 | 入口 | 用途 |
|---|---|---|
| GitHub Discussions | <https://github.com/deepseek-ai/deepseek-harness/discussions> | 提问、反馈、bug、Show Your Plugins |
| `dsh-plugin` topic | <https://github.com/topics/dsh-plugin> | 让你被搜到（官方 README 建议每个插件仓库都打） |
| 企微群 | 官方 README「社区与支持」的**入群问卷** | 中文用户 / 开发者交流（小助手定期发邀请） |
| 微信公众号 | 官方 README「社区与支持」的二维码 | 公告 / 文章 |
| Oh My DSH | <https://github.com/omdsh-dev> · <https://omdsh.dev> | 非官方开发者社区，插件作者聚集 |

**发一条插件介绍（可选）**：官方 Discussions 的 `Show Your Plugins!` 分类是常见的发现入口。**分类名会被维护者改，别写死**——先查当前分类：

```sh
gh api graphql -f query='{ repository(owner: "deepseek-ai", name: "deepseek-harness") {
  hasDiscussionsEnabled discussionCategories(first: 20) { nodes { name slug } } } }'
```

```sh
gh discussion create --repo deepseek-ai/deepseek-harness \
  --category show-your-plugins \
  --title "<插件名>：<一句话价值主张>" \
  --body-file /tmp/plugin-announce.md
```

正文骨架（一屏读完；比 README 短，只负责"要不要点进去"）：一句话是什么 + 解决什么 → 安装命令（生效条件以目标环境验证为准）→ 一张截图或两三行效果 → 仓库链接。

礼仪（比格式重要）：**一个插件一条**（更新就编辑原帖，不重复发）；**仓库先公开**（否则 404）；**标题不堆词**（与仓库 description 同一纪律）；**认真回帖**；⚠️ 对外可见动作，**发布前要有用户明确同意**。

## D 社区目录、市场与工具

| 角色 | 入口 | 说明 |
|---|---|---|
| 精选列表 | <https://awesome-dsh-plugin.com>（仓库 `awesome-dsh-plugin/awesome-dsh-plugin`） | 社区热门精选列表，人工分类 |
| **市场索引** | <https://dshmarket.com/index.json> · <https://awesome-dsh-plugin.com/index.json> | 都是 `format: 1` 索引，可直接加进「发现」；两者条目数一致（约 3k），是同一份精选目录的两个入口 |
| 市场索引（较小） | `raw.githubusercontent.com/bruc3van/awesome-dsh-plugin/main/data/dsh-market-index.json` | 另一份 `format: 1` 索引（约 600 条，标题「DSH Community Market」）；与上面不是同一份，按需选 |
| 应用内市场 | <https://dsh.market>（`2BingLing/dsh-market`）· <https://dsh-plugin.org>（`dshplugin/dsh-plugin-hub`）· `LivXue/dsh-plugin-shop` | 自带搜索 / 评分 / 一键安装；`dsh-plugin.org` 另有网页版插件页、一键安装与 `listed` 徽章；收录量与评分口径由各家自述 |
| 目录 + 安装审计 | <https://dshbase.com> | 约两万条目，声称 L1–L4 安装测试；审计基线较旧（0.1.0-rc.6），且按 topic 抓取会混入非 dsh 项目 |
| 聚合浏览站 | <https://dshget.com> | 把多个目录聚合到一个网站（awesome-dsh-plugin / hrhgit catalog / OMDSH Hub / GitHub topic），可浏览检索；**没有 `index.json`，不能当「发现」的索引源** |
| 生态 Hub | <https://deepseek.stream> | 社区 Hub：插件页、一键安装、榜单与论坛；非官方 |
| 质量评分 | <https://github.com/PerryLink/dsh-score> · <https://perrylink.github.io/plugins/dsh-score/> | 对插件仓库 / npm 包做多维评分 |
| 生态雷达 / 发现 | <https://github.com/AdamPlatin123/dsh-plugin-radar> · <https://github.com/awesome-dsh-plugin/dsh-find-plugin> · <https://dshfind.com> | 持续发现新插件；`dsh-find-plugin` 可在 agent 内搜索；dshfind 每日同步 star / 增长 / 评分并提供徽章与课程 |
| 升级工具 | <https://github.com/oh-my-dsh/dsh-plugin-upgrade-skill> | 让插件跟随 dsh 版本升级（与 [09-dev-conventions.md](09-dev-conventions.md) 的兼容性纪律互补） |
| 第三方桌面端 | <https://dshdesktop.com>（`dataelement/dsh-desktop`） | 打包 dsh 的社区桌面应用；**与官方 Desktop 不是同一产品**，插件管理与版本跟随都不同（官方 Desktop 见 [14-desktop.md](14-desktop.md)） |

⚠️ 三条使用警告：

1. **收录 ≠ 安全 ≠ 兼容**：这些目录/市场都是第三方，DSH 只校验索引格式；装前看来源、看 `engines.dsh`、必要时 pin commit。
2. **`dsh-plugin` topic 被大量无关项目占用**：按 topic 抓取的目录（包括 dshbase）里常见并非 dsh 插件的大项目；判断标准是它是否真声明 `dsh.bundle` / 是否真在 dsh 里跑起来。
3. **两个名字很像的站**：`dshmarket.com`（市场索引）与 `dsh.market`（应用内市场）不是同一个，别混。

## E 发现与参考实现

```sh
# 最近还在更新的 dsh 插件仓库（topic 有噪声，结果要人工筛）
gh search repos --topic dsh-plugin --sort updated --limit 20
# 官方 discussion 分类（名字会变，先查）
gh api graphql -f query='{ repository(owner: "deepseek-ai", name: "deepseek-harness") {
  hasDiscussionsEnabled discussionCategories(first: 20) { nodes { name slug } } } }'
```

参考实现（公开仓库，看它们各自示范什么）：

| 仓库 | 示范 |
|---|---|
| `vlln/whale-girl` | bundle + `__ModuleLoader__.load` client + 设置页配置卡片的完整例子 |
| `vlln/dsh-loop` | 工具 + client 状态条的最小例子 |
| `vlln/plugin-registry` 的 `packages/plugin/console` | 薄控制台 / 多层 patch 的组织方式 |
