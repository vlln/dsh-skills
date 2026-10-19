# 交付检查与发布

> **本文件回答**：交付检查清单、公开发布的写法（description / topics）。**不回答**：市场与社区（→ 12）、验证方法（→ 10）。

**来源**：本 skill **自定**（非官方文档派生）——交付清单、README 发布纪律、仓库 description / topics 规则与官方 Discussions 礼仪；官方发布渠道见 `docs/user/develop/basic/publish.md`。复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

本页是「做完插件之后」的动作：先过**交付检查清单**（与是否公开发布无关），再决定要不要公开分发。安装通道与验证方法在 [10-install-and-verify.md](10-install-and-verify.md)。

## 交付检查清单（做完插件就过一遍，与是否公开发布无关）

- [ ] `package.json#main`/`exports` 指向 entry；`dsh.bundle.patch` → `cordis.patch.yml`；
      insert 行与包名同源；**依赖三字段为空**（[13-gotchas.md](13-gotchas.md) 1）
- [ ] 已绘制插件图标；顶层 `icon`、打包包含与 manifest 导出正确；真实 Plugins 页图片
      加载通过，且完成实际视觉检验（[SKILL.md](../SKILL.md) Step 2b；机械验证不能替代看图）
- [ ] 带 UI 时过了 [06-ui-style.md](06-ui-style.md) 的**交付前视觉自检**：浅色/深色各看一次、
      没有写死颜色、焦点与 disabled 态齐、圆角按角色选档、能复用官方控件的地方没有自绘
- [ ] 门禁通过（`scripts/gates/run.mjs`）——仓库自带门禁，含自证测试
- [ ] README 按 [templates/README.md](../templates/README.md) 的骨架写（安装含具体 ref 与 GUI 入口、使用、能力表、配置、限制、插件管理、兼容性）；有网络/执行/写文件时含「安全与数据」
- [ ] README 有 **`## 兼容性`** 节，写清**实测支持的 dsh 版本 + 验证日期**，且与
      `peerDependencies` 的官方范围同源（规范见 [SKILL.md](../SKILL.md) Step 6）
- [ ] README **只含面向使用者的内容**——工程备忘录（机制/验证证据/踩坑）已移到
      `AGENTS.local.md`、代码注释或 `docs/engineering-notes.md`，README 只留一句指针
- [ ] **安装冒烟含一次真实工具/命令调用**（boot 干净 ≠ 功能可用），且做过负控
      （[10-install-and-verify.md](10-install-and-verify.md)「三条硬规矩」）

## 公开发布（可选）

**只给自己或团队用、或用 git 源 / 本地目录分享，都不必发布**——下面是决定把插件公开分发
（GitHub / npm）时才做的动作；不打算公开可以跳过本节，上面的交付检查清单仍然要过。

**仓库 description**——**只写"这是什么、能干什么"，一句话让用户在搜索结果里一眼看懂**：

```
<插件做什么>：<用户视角的收益/场景>（DeepSeek Harness 插件）
```

- **不要往里塞安装命令、包名、生态术语堆砌**（`dsh plugin --profile web add github:…`
  这类样板属于 README 的安装节，不属于 description）——搜索列表里只有一行位置，
  塞进去的都是用户读不完、也用不上的字节。用户 2026-09 拍板：
  "description 中应该仅有让用户一眼清晰理解项目的描述"。
- 中文优先（受众主要是中文用户）；双语可选，英文在前利于国际发现——但**别把两句都写进去挤成一段**。
- 例（`dsh-autofork`）：`Agent 忙时自动分叉会话：你新发的指令立刻在新会话里得到响应，旧会话留在后台跑完并把结果回注（DeepSeek Harness 插件）`

**仓库 topics（GitHub 标签）**：打标签便于 `gh`/搜索/发现。两类组合：

**必选 2 个**（生态身份，一个都不能少）：
- `dsh-plugin`——dsh 插件的通用检索词（用户会直接搜它）
- `deepseek-harness`——标明上游宿主

**功能标签 1-3 个**（描述插件实际做什么，是区分度的来源）：
- 能力：`tool` / `skill` / `mcp` / `command` / `ui`（按插件含什么）
- **领域/用途**（关键——让搜索命中「能干什么」）：如 `pet`（宠物）、
  `loop`（定时循环）、`terminal`（终端）、`status`（状态条）、`automation`
  （自动化）、`workflow`（工作流）等——从插件的核心功能提炼 1-2 个具体
  领域词，避免泛词
- 形态：`agent` / `agents`（agentic 上下文，可选）

**原则**：想象用户搜什么词能找到这个插件——`dsh-plugin` 是身份，
`<你的功能词>` 才是区分度。标签总数 3-6 个（必选 2 + 功能 1-3）。

用 `gh repo edit <owner>/<repo> --add-topic dsh-plugin --add-topic deepseek-harness
--add-topic <功能词> ...` 打标签。

**公开发布的补充检查**：
- [ ] 面向用户的安装说明**只给 git 源**（零依赖包的本地目录装有前置条件，见
      [13-gotchas.md](13-gotchas.md) 6）
- [ ] 仓库 description = 一句话"是什么 + 能干什么"（**无安装命令样板**）
- [ ] 仓库 topics 至少含 `dsh-plugin` 与 `deepseek-harness`，另加 1-3 个功能词

## 发布之后：被看见（可选）

想去插件市场或社区曝光：见 [12-ecosystem.md](12-ecosystem.md)——市场索引机制、社区入口、社区目录与工具都在那里。**本页只管"发得对"，不管"发到哪"。**
