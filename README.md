<h1 align="center">dsh-skills</h1>

<p align="center">
  <strong>DeepSeek Harness（dsh）开发与维护的 agent skills 集合。</strong><br/>
  面向「给 dsh 写插件的人」与「dsh 会话坏了要修的人」——每个 skill 都能被
  <a href="https://github.com/vlln/skit">skit</a> 直接安装。
</p>

## Skills

| Skill | 作用 |
|---|---|
| `make-dsh-plugin` | 开发 dsh 插件：形态选择（skill 包 / MCP / Node 工具 / 浏览器 UI / 组合层）、npm 包与 entry 契约、client bundle、设置页集成、安装与验证纪律、发布与生态纪律 |
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
