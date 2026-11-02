# 工作目录迁移：当宿主目录被改名或移动

> 实测基线：dsh `0.2.1-rc.5`、macOS（APFS，大小写不敏感）、2026-11-02。
> 证据来自一次真实的 home 目录重命名：`~/Project`→`~/Projects`、
> `~/GithubProjects`→`~/External`、`~/agent-space`→`~/Workbench`、
> `~/personal-data`→`~/Personal`，波及 4 个 DSH_HOME、1895 个会话日志。

## 症状

```
working-directory: directory does not exist: "/Users/<you>/Project/<project>"
```

每个“以前的会话”都这样，新建的会话正常。日志本身没坏：`check-session.py`
报 OK，`verify-session.mjs` 也能正常打开它。

## 为什么

`@deepseek-ai/dsh-working-directory` 的 `ensure()` 每轮开始时：

1. 取会话的当前工作目录（projection 状态，初值 = header `cwd`）；
2. `fs.resolve` + `fs.stat`；存在就继续；
3. 不存在 → 回退到「会话原始目录」`header.cwd`；
4. 原始目录也不存在 → `throw new Error("working-directory: directory does not exist: …")`。

旧会话的“当前目录”和“原始目录”是同一个已经消失的路径，所以第 4 步必然发生。
换句话说：**这不是日志损坏，是一个路径解析死局**；把路径恢复成存在，会话立刻能开。

同一根路径还绑着另外三份状态，它们坏了会以完全不同的症状出现：

| 绑定 | 代码依据 | 后果 |
|---|---|---|
| 日志目录名 | `projectKey(cwd)`（`dsh-session-persistence-jsonl`） | 只影响“新会话落在哪个目录”：`findLog()` 会遍历所有项目目录按 header 找日志，`open()` 用找到的目录继续追加，所以不搬也能跑，只是同一项目的会话会分裂到两个目录 |
| `workspace.json` 的 `path` | `WorkspaceRegistry`：`candidateMatches(id, path)` 比 `sessionPaths.get(id) === path` | 侧边栏归组全部落空，会话“消失” |
| `session_projcache` 的 `identity.cwd` | `identityMatches` / `currentLifecycleMatches`：`createdAt` + `cwd` + `isSeeded`（`formatVersion` 决定能否做 fold 快捷） | 侧边栏**全部显示「未命名」**——列表只读缓存标题，不读日志 |

最后一条是最容易被误判成“数据丢了”的地方。标题其实有两份：日志里的
`session/title` 事件（`dsh-session-title` 的 `apply` 折叠）和投影缓存里的
`rows.title.val`。缓存失效只损失“列表廉价的标题提示”，打开会话冷读一遍就会重建；
但只要缓存不修，不打开就永远是「未命名」。

## 顺序

1. **备份**：受影响的 session 项目目录（tar 即可，日志已压缩）、`workspace.json`、
   `session_projcache*`。实测 2.2G / 1895 个日志，tar 约 1 分钟。
2. **`migrate-cwd.py`**：改 header `cwd` + `working-directory/change` 事件里的 `cwd`。
   - 正文一个字节都不动（seq / 回合结构契约与正文无关），只替换 JSON 里的路径值：
     用 `'"cwd":' + json.dumps(old)` 精确匹配，避免误改消息与工具输出里的历史文本。
   - 重编码按 harness 自己的 framing：header 行单独一个带 checksum 的 zstd frame，
     其余事件一个 body frame。写回后**解压回来逐字节比对**，不一致就写了临时文件不发布。
   - 一条日志可能有上千个 frame（每次 append 一个），重编码成 2 个 frame 是安全的：
     scanner 只要求“每个完整 frame 里是完整 JSONL 记录”，不要求 frame 数与写入节奏一致。
   - 目标目录必须存在，否则跳过并报告 `missing-target`（宁可不迁，不要指向不存在的路径）。
3. **`rekey-dirs.py`**：按新的 header `cwd` 重算 `projectKey`，把会话目录 rename
   过去（同一文件系统 = rename，很快；1669 个目录约 10 秒），并删掉空的旧项目目录。
   按**每个会话**分别搬，而不是整个项目目录整体搬：旧目录里可能混着不同 cwd 的会话
   （历史遗留），整体搬会把它们塞错地方。
4. **`migrate-workspaces.py`**：重指 `path`，处理撞车。
5. **`fix-projcache.py`**：重指 `identity.cwd`（逐记录 + 旧的单文件 `session_projcache.json`）。
6. **重启 dsh server**：两份注册表都在 boot 时读进内存，不重启看不到效果。
7. **验证**：`verify-session.mjs` 抽样 + `check-session.py --all` 对比“改前/改后”的
   违规集合（应当完全一致）。

## 映射怎么定

- **能验证就验证**：新路径必须存在（脚本对 header 目标做 `isdir` 检查，失败就跳过）。
- **删掉的东西不要凭空造**：某项目的 `hub/` 子目录在清理时被当空壳删除，5 个会话的
  cwd 无处可去 → 指到父项目（`dsh-plugins`），因为它们本来就在那个作业区里工作。
  另一批 `~/Documents/new-project` 是早已删除的临时目录 → 保持原样（继续坏着，
  但不要指向一个语义无关的目录）。
- **大小写不敏感的文件系统**：`~/references` 与 `~/References` 是同一个目录。
  `mv` 不需要，也不要为它造映射；但 `realpath` 出来的规范路径才是
  `workspace.json` / `identity.cwd` 该写的值。
- **一个旧根的子树要能整体映射**：`map(old_parent/child)` 用前缀替换，
  前提是“改名只换了根、子树结构不变”。若子树也动了，就在映射表里单独列一条更长的旧前缀
  （脚本按最长前缀优先匹配）。

## `workspace.json` 的两条硬规则

1. **同一 canonical path 不能有两条记录。** 重命名后 `hub` 撞上 `dsh-plugins`、
   `agent-space` 撞上 `Workbench`——registry 启动时按路径唯一性校验，撞车是 boot 期缺陷。
   合并方式：保留“目标路径已有”的那条，把旧记录的 `sessionIds` 去重追加进去，
   从 `tables.workspaces` 和 `global.workspaceIds` 里删掉旧 id。
2. **它是内存态，不是文件态。** registry 在 boot 时读入，之后整文件重写。所以
   改文件必须配一次重启；重启前用户在 GUI 里新建/删除/拖动工作区会触发整文件写回，
   把旧路径写回来。脚本是幂等的，真发生就再跑一次。

标题同理：`title` 只是显示名，默认值来自目录 basename，旧标题会留着
`Project` / `personal-data` 这种名字；`migrate-workspaces.py` 不自动改（用户可能自己
重命名过），需要时单独改——判断依据是 “title 恰好等于旧 basename 才改”。

## 投影缓存：为什么必须改，怎么改才安全

- 逐会话一个文件：`~/.dsh/storages/session_projcache/sessions/<id>.json`，
  外加旧版的单文件 `session_projcache*.json`（domain version 3，仍作为 predecessor 可读）。
- 记录形如 `{version, record: {identity: {formatVersion, createdAt, cwd, isSeeded,
  inheritedEventCount}, rows: {title: {ver, seq, val}, …}}}`。**只改 `identity.cwd`**，
  `rows` 一律不动——`rows` 是投影状态，改了就是伪造。
- **不要 `json.dump(..., ensure_ascii=False)`**：个别标题文本是“按 code unit 截断”的
  产物，含孤立代理项（如 `\ud835`），Python 无法用 UTF-8 编码，`json.dump` 直接抛
  `UnicodeEncodeError` 并中止整批。用 `ensure_ascii=True`：转义形式是同一个 JSON 值，
  所有读取方都按 JSON 解析，语义不变。
- 原子写：临时文件 + `fsync` + `os.replace`，权限 600（目录本身是 700）。中途失败
  只会留下临时文件，原记录完好。
- 校验方法（不依赖 GUI）：逐条比较缓存 `identity` 与日志 header 的
  `createdAt` / `cwd` / `isSeeded`。注意 **v0 老日志的 header 没有 `isSeeded` 字段**，
  harness 迁移后按 `false`（seeded 日志按 `true`）解释——手写校验时按这个缺省处理，
  否则会误报一批“不匹配”。
- 实测结果：1858 条记录 → 1826 条直接对齐、31 条 seeded（v0 header 无 `isSeeded`）、
  1 条是无日志的孤儿记录；1765 条有标题，93 条本来就没标题。修好后重启，标题全部回来，
  没有任何标题需要重新生成。

## 活会话（flock）

会话打开时 `dsh-session-persistence-jsonl` 在会话目录里拿一把内核写锁
（`session.lock`）。迁移前用 `fcntl.flock(LOCK_EX|LOCK_NB)` 试一下：拿不到 = 有客户端
正在用它，**跳过**。跳过之后用 `--force-live` 强迁只有一个安全场景：这个会话因为
自己的 cwd 没了而**根本起不了一轮**（无 append）。此时强迁要同时告诉用户：
重启前别在那个标签页里发消息——活动句柄仍指向旧 inode，append 会写进已取消链接的文件。

注意 GUI 重启会把上次打开的标签页恢复成活动会话，于是“关掉标签→跑脚本”常常又变成
“被锁住”。要么在重启前跑完，要么用 `--force-live` + 明确警告。

## 验证与回归证据

- `verify-session.mjs`：把日志复制到临时 store 的**正确项目目录**下（store 会拒绝
  “header 与位置不符”的归档），挂载已安装的 `dsh-session-persistence-jsonl`，
  只读打开。当前版本必须用“挂载插件”而不是 `new JsonlSessionPersistence(...)`
  ——后者在 0.2.1-rc.5 上抛 `TypeError: … is not a constructor`。
- 回归判定：把**改名前的原件**（备份 tar）解到临时目录，用同一个 verifier 全量跑一遍，
  比较失败集合。实测 v0 767 个：改前（备份范围内 756 个）341 个失败、改后 767 个 347 个失败，
  多出的 6 个全是备份范围外、本次没碰的目录 → 零回归。这些失败是**当前 dsh 拒绝旧 v0
  格式**（`unsupported descriptor version N`、`format v2 surface before first step …`），
  与改名无关，改名前后表现一致。

## 第二种形态：会话搬了自己的 cwd

真实事故的第二波（同日 4 小时后）：一个负责“整理 home 目录”的会话，在被清理的
`~/Projects/dsh-plugins` 里工作，并在同一轮里把它改名成 `~/Projects/DshPlugins`（同时把
`repro-decision-provenance` → `Repro/…`、`skill_project` → `Skills`、`llm-gateway` →
`LlmGateway`）。**那一轮成功结束**，下一轮一开始就 `working-directory: directory does not
exist`——路径被它自己搬走了。

特征与处置：

- 日志最后两条是 `turn/start N` + `turn/end N {reason: error}`：说明是“这一轮起不来”，
  日志结构完好，不需要 `repair-session.py`。
- 同一个 mapping 表 + 同一套脚本直接复用（这次 1239 个日志、1229 个目录、4 条 workspace
  记录、1398 条缓存身份），全程没有新代码。
- 肇事会话通常还开着 → `flock` 拿不到 → 它对安全（本来就起不来）用 `--force-live`，
  并提醒用户重启前别在那个标签页发消息。
- 结构性建议：**目录搬迁要在中立 cwd 里做**（`~/Workbench`、`~`），或者每搬一次就
  “迁移 + 重启”再继续；否则任务本身会周期性自杀。

## 不要走的捷径

- **给旧路径建符号链接**（`~/Project -> ~/Projects`）：能让所有旧会话立刻能开，但
  header、`workspace.json`、缓存 `identity.cwd` 仍全是旧路径，等于永久留一个别名层；
  日后一旦删掉链接就全体复发。只适合“先止血、稍后正经迁”。
- **只改日志、不改 GUI 两份状态**：会话能开，但侧边栏空/标题全「未命名」，用户会以为
  数据丢了。
- **直接删缓存让它重建**：标题不在日志里吗？在。但“让列表重新读 1895 个日志”这件事
  没有廉价路径，标题提示会一直空到每个会话被打开；改 `identity.cwd` 才是零成本恢复。
