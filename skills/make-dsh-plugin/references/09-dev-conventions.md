# 纪律与开发规范

> **本文件回答**：必须遵守的纪律（依赖 / 层归属 / 验证 / 基线 / 发布卫生）。**不回答**：每条纪律的证据（→ 13）、具体操作（→ 10）。

**来源**：本 skill **自定**（非官方文档派生）——插件仓库该有的工程纪律；官方仓库自身的对应实践见
`.agents/notes/`（决策记录）、`scripts/`（门禁）、`docs/testing.md`，需要时以它们为准。
复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

**定位**：这一篇是「习惯与约束」层的唯一真源。前 11 条是**动手前必须过的速查表**，后面是细则；
每条纪律都能指到一个反例或证据（证据在 [13-gotchas.md](13-gotchas.md)）。

## 11 条纪律（速查）

| # | 纪律 | 为什么 | 细则 |
|---|---|---|---|
| 1 | 分清宿主运行时、开发 SDK、第三方运行依赖与兼容约束 | 不内嵌第二份宿主内核/React；不以三字段空替代解析与安装验证 | [05-bundle-plugins.md](05-bundle-plugins.md)「依赖解析」 |
| 2 | 在实际分发安装位置验证解析 | 树外 link 缺 SDK 时可能整树失败，也可能宿主起来但插件未激活；不能只看首页 | [13-gotchas.md](13-gotchas.md) 6 |
| 3 | 启停覆盖写 profile 层，不写进 bundle 包内 | 产品层定义组合行，用户层承载偏好；写错层会被下次升级覆盖 | [13-gotchas.md](13-gotchas.md) 1b |
| 4 | 覆盖某行必须重述整块 `config` | patch 按行整块替换，不是深合并——漏字段 = 丢配置 | [13-gotchas.md](13-gotchas.md) 1b |
| 5 | `config.id` 是身份，发布后不改；preset 行 id 用 `preset-<id>` | 会话按 id 恢复，改了就拒绝恢复；行 id 是 Loader 编辑地址 | [02-profile-and-preset.md](02-profile-and-preset.md) §2.3 |
| 6 | 改动按改动面取**最窄**证据，并先做负控 | "干净日志"只有在故意弄坏会响亮报错时才算证据 | [10-install-and-verify.md](10-install-and-verify.md)「三条硬规矩」 |
| 7 | boot 干净 ≠ 功能可用：真调一次核心功能 | 服务惰性读取、严格注入的两类错都可能在 boot 期沉默 | [13-gotchas.md](13-gotchas.md) 3 |
| 8 | 资产从安装包解析，不读 profile / preset 目录 | preset 没有自己的目录；写死相对路径在安装形态下必坏 | [02-profile-and-preset.md](02-profile-and-preset.md) §2.6 |
| 9 | 时效知识分家：机制带版本号；渠道 / 社区 / 生态现状**只进 12**（写"是什么/怎么用"，不写"最新/N 个"）；复核节奏归项目 README | "最新版 / 社区在 X / 市场有 N 个"是断言，会烂掉；"在 0.x 实测"是记录 | [SKILL.md](../SKILL.md)「溯源」、[12-ecosystem.md](12-ecosystem.md) |
| 10 | README 只写使用者内容；工程备忘录进 `AGENTS.local.md` / `docs/engineering-notes.md` | 读者不对，关键信息会被淹掉（反例：602 行 README，安装节在 573 行） | [SKILL.md](../SKILL.md) Step 6 |
| 11 | 自动回归用临时隔离站；人工验收用持久私有站与稳定端口；不复用主 GUI | 自动测试保证干净，人工测试保留会话；按项目规则取得路径与权限，不自行覆盖真实数据 | [10-install-and-verify.md](10-install-and-verify.md)「本地开发实例」 |

## 门禁

- 机械检查 + 自证测试：每个门禁有用非法样例证明会拒绝的测试。
- 在插件仓库声明一个真实存在的统一检查命令（如 `npm run verify`），列明其包含/不包含的测试；不要假设固定的 `scripts/gates/run.mjs` 已存在。按改动面跑**最窄**证据，发布前跑完整声明的门禁。最低覆盖见 [16](16-engineering-patterns.md)。
- 常见门禁：md-links / decisions / assets / spec-states / config-sync / generated-freshness / unit-tests / gate-self-tests，外加两类实战发现值得默认带的：
  - `package-contract`——入口与 bundle patch 指向真实文件、`cordis.patch.yml` 的 insert 行与包名**同源**；依赖用途与 external 按 [05](05-bundle-plugins.md) 校验，不用「字段必须为空」作门禁。这类"包名三处同名"的契约靠人眼盯很容易漏。
  - `no-machine-paths`——**发布卫生**：入库文件不得含本机绝对路径与凭据（发布前扫一遍，比事后从历史里清便宜得多）。

## 决策记录

- 每个非平凡改动随附决策记录（`decisions/implemented/...`）：
  `## Problem` → `## Decision` → `## Alternatives considered` → `## Consequences`。
- 决策分类封闭集合：feature / bug-fix / simplification / architecture / process / testing。
- 部分取代旧决策时两条保持活跃并互链。

## 生成物纪律

- `client.js` 由构建生成（`build-client.mjs --check` 守卫新鲜度），勿手改。
- 生成物不手改——改源码，重新构建。

## 环境行为沉淀

宿主/平台环境性行为首次复现即沉淀：如「宿主会清理/覆盖 CSS 注入样式」这类环境事实，第一次踩坑就写 bug-fix 决策记录标注「环境事实」，不等第 N 次再固化。

## 兼容性标注（每次改动都过一遍）

- README 的 `## 兼容性` 节是**对外承诺**：每次改动后自问一句"这次改动还成立的 dsh 版本变了吗"——
  改了机制挂钩点 / client 契约 / 设置面（服务名、槽名、manifest 字段、平台种子模块导出名）就
  **重新实测并更新版本号与日期**；纯文案与内部重构不动它。
- 证据留在本地（`AGENTS.local.md` 或仓库内 `docs/engineering-notes.md`）：写清**在哪个版本、怎么验证、
  看到什么**；README 只写结论。**不要**把会过期的上游断言（"最新版"、"当前基线是 X"）留在
  README 或代码注释里——那是断言，不是实测记录。

## 协作约束

- 一个 PR 一种性质 + 标签；独立改动拆开；缺陷在引入它的 PR 上修。
- 并行/在途改动保护：`git status` 有未暂存改动时禁用 `git add -A`——显式路径 add。
- 未被明确要求时不推送、不合并、不发布。
