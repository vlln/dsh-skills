# make-dsh-plugin（维护者文档）

> 这份 README 给**维护这个 skill 的人**看，不参与 agent 加载（agent 读的是 `SKILL.md` 与 `references/`）。

## 结构纪律

- `SKILL.md` 只做入口：30 秒版概念 → 路线选择 → 边界地图 → Step→文件 → 11 条纪律。**不堆细节**。
- `references/` 用两位序号命名，序号就是目录顺序（01 概念 → 13 证据池 → 14 Desktop），但**不要求线性阅读**：每个文件在开头自报「本文件回答 / 不回答 → 去」。agent 按问题取一篇，不按顺序读。
- **一个事实一个家**：概念在 01、装配机制在 02、契约在 04/05、纪律在 09、验证在 10、发布在 11、生态与时效数据在 12、证据在 13。别处只放指针。
- 每个 reference 必须有一行「来源」（官方路径 / 实测基线 / 本 skill 自定），口径与 `SKILL.md` 的「溯源」一致。
- 新增 reference 时：用下一个序号、加边界框、加来源、更新 `SKILL.md` 的边界地图与参考列表；**不要加"上一篇/下一篇"导航行**——agent 自己会导航。
- `templates/` 放可复制的骨架（当前只有 `README.md`），不属于 references；不要给它编号。

## 保鲜协议（时效知识）

**哪些内容会过期**：`12-ecosystem.md` 的全部条目（社区入口、市场索引、生态项目）、`11-publish.md` 的外部事实、`SKILL.md` 里的版本标注，以及 `05` 的渠道行为。

**复核触发**（满足任一）：

- dsh 发布新 rc / 基线升级；
- 距上次复核 > 60 天；
- 任一入口 404、命令输出与文档不符、市场机制改名。

**复核动作**：

```sh
npm view @deepseek-ai/dsh dist-tags                       # 当前通道与版本
gh api graphql -f query='{ repository(owner: "deepseek-ai", name: "deepseek-harness") {
  hasDiscussionsEnabled discussionCategories(first: 20) { nodes { name slug } } } }'
curl -sSI --noproxy '*' https://dshmarket.com/index.json  # 逐个入口查 2xx
```

外加：确认 `@deepseek-ai/dsh-experimental-plugin-market-bundle` 仍在可选 bundle 名单、「发现」页路径未变。

**更新范围**：只改 `12-ecosystem.md` 的数据与 `SKILL.md` 的版本标注；**不要把时效结论写进 01–11 或 13 的正文**。写的时候只写"是什么 / 怎么用"，不写"最新""第一""有 N 个"这类会烂掉的断言。

## 已核记录（2026-10-18，安装版 dsh 0.2.1-rc.1）

复核方式：对安装版包做符号检索、读 `lib/types/*.d.ts`、跑 `dsh --help` / `--dump-*`。

**0.2.1-rc.1 已确认**：`webServer`（`httpServer` 已不存在）；`settings.describe()` 的 `value` / `user` / `revision` 字段；`agentPresets`、`uiWorkspace.openSession`、`commandUi`、`configForms`；`ctx.locale` 的 `register` / `addLanguage` / `bind` / `resolveText` / `getSnapshot`；manifest 的 `icon`（≤ 256 KiB，SVG/PNG/JPEG/WebP）、`dsh.bundle.patch` 数组、`dsh.client.{platform,inject,external,immediately}`、`manifestVersion: 1`；CLI 的 `--from-default-profile` / `--dump-config-schema` / `--no-open`；市场 bundle `@deepseek-ai/dsh-experimental-plugin-market-bundle`；`HOST_FACES`、`data-width-handle`、`staticModules`（0.2.1 的类型名，0.2.0 叫 `getStaticModules()`）；`dsh.skills` 无消费方、`dsh.mcpServers` 不是 manifest 字段；06 的 token 名称与解析值（bg/label/border/hover/menu）、圆角数值、组件名；07 的槽名与 `view: summary|page`；10 的 HMR 语义（profile 重组会替换 `node_modules`/link 里的文件变化，无需 root 监听）；`CommandDescriptor` 字段、`HOST_FACES` 六个内置 id、`commandUi` 公开方法（`register/decorate/dismiss/popupFor`，`candidates` 为 private）、v4 的 `producerKind` / `assertAssistantSettlementShape`、`jobs.list(sessionId)`、`agent/disposed { agent }`。以上均以 0.2.1 复核。

**未在本机实测**：14-desktop 依据官方 `apps/desktop/README.md`（master `0.2.1-rc.2`）与共享插件管理器文档编写，未在打包版 Desktop 上逐条跑；改动 Desktop 行为时按同文件重核。

**本地开发实例实测（2026-10-20，安装版 0.2.1-rc.1）**：`dsh plugin --profile web add <本地目录>` 在隔离 `DSH_HOME` 里生成 `link:` 依赖、并把 bundle 自动追加进 `dsh.profile.bundles`；`dsh web --port 0` 的启动行打印 `http://127.0.0.1:<随机端口>/?token=…`。**树外 link 的官方包解析**：插件自己 `node_modules` 没有 SDK 链接时实例照常启动、插件静默消失（日志 `failed to import … Cannot find package 'cordis'` + `warning: 1 entry did not activate`）；补上 `@deepseek-ai` 与 `cordis` 链接后正常装载、无警告。以上写入 [10-install-and-verify.md](references/10-install-and-verify.md)「本地开发实例」。

**仍保留 0.2.0-rc.2 标注（未按 0.2.1 重核）**：06 的组件逐条 props 与几何（槽位尺寸、间距）；07 的渲染契约细节（hooks 顺序、chrome 归属）；10 的图标验收路径细节；13 里 0.1.5 时段的实例与 0.2.0 迁移表。重核时按上面的「复核动作」逐条跑，并在本文件追加日期。

## 版本

- `SKILL.md` frontmatter 的 `metadata.version`：结构或口径变化 bump major，内容补充 bump minor。
- 当前版本见 `SKILL.md`。

## 自检

```sh
# 相对链接是否都落到真实文件（忽略代码块里的伪路径）
python3 - <<'PY'
import re, os, glob
bad = []
for f in ['SKILL.md'] + sorted(glob.glob('references/*.md')):
    d = os.path.dirname(f)
    text = open(f).read()
    text = re.sub(r'```.*?```', '', text, flags=re.S)   # 代码块里的伪路径
    text = re.sub(r'`[^`\n]*`', '', text)               # 行内代码（如 @[label](dsh-session:…)）
    for m in re.finditer(r'\]\(([^)#\s]+)(?:#[^)]*)?\)', text):
        t = m.group(1)
        if t.startswith(('http', 'mailto')): continue
        if not os.path.exists(os.path.normpath(os.path.join(d, t))): bad.append((f, t))
print('\n'.join(f'{f}: {t}' for f, t in bad) or 'all links ok')
PY
```
