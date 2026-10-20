<h1 align="center">dsh-skills</h1>

<p align="center">
  <strong>DeepSeek Harness（dsh）开发与维护的 agent skills 集合。</strong><br/>
  面向「给 dsh 写插件的人」与「dsh 会话坏了要修的人」——每个 skill 都能被
  <a href="https://github.com/vlln/skit">skit</a> 直接安装。
</p>

## Skills

| Skill | 作用 |
|---|---|
| `make-dsh-plugin` | 开发 dsh 插件与垂直 Agent：**概念地图**（profile / bundle / plugin / agent preset / skill 五种装配单位，宿主树与 per-Agent 树）、形态选择（bundle / 纯 cordis / 纯 skill 包 / MCP）、**从零搭垂直 Agent 的三步法**（工具 → preset → UI + profile）、npm 包与 entry 契约、client bundle 与插件 UI 风格、设置页集成、安装与验证纪律（**本地开发实例**：独立进程 + 随机端口 + 用户手动验收）、交付检查与发布规范、**生态与渠道索引**（插件市场 / 社区 / 社区索引源） |
| `dsh-session-repair` | 修复在 GUI 中打不开的 dsh 会话历史：检测 seq 重复与回合结构损坏，修复后用 harness 自身的持久化代码验证 |

两个 skill 各自独立——装哪个用哪个，没有相互依赖。

## 安装

```sh
skit install github:vlln/dsh-skills --all        # 全部
skit install github:vlln/dsh-skills@make-dsh-plugin   # 只装一个
```

本地开发时直接装目录：`skit install ./dsh-skills --all`。

## 仓库结构

```
skills/<name>/SKILL.md        # 技能本体（agent 读的入口）
skills/<name>/references/     # 深读材料（SKILL.md 到对应阶段时指过去）
skills/<name>/scripts/        # 技能自带脚本（LLM 无法凭常识推出来的工具）
```

`skills/` 是产品；仓库根的 README 面向使用者，不描述 agent 内部工作流。

## 许可

MIT
