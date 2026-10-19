# Entry 契约详情（Cordis entry + skill + MCP）

> **本文件回答**：`package.json#dsh` / Cordis entry / client half / skill / MCP 的契约。**不回答**：打包与 Git 安装（→ 05）、安装验证（→ 10）。

**来源**：官方 `docs/user/develop/framework/*`（服务与事件契约）、`docs/cookbook/adding-a-package.md`、
`packages/mcp/mcp-client/README.md`（MCP 字段）；`dsh.skills` 无消费方、命名导出被 `unwrapExports` 遮蔽这类
**实测**结论标在各条内。基线 **0.2.0-rc.2**（2026-10-15 核）。复核方法见 [SKILL.md](../SKILL.md) 的「溯源」节。

本文件是 make-dsh-plugin 的**自带权威契约**（skill 独立分发，不依赖仓库文档）。bundle 形态完整契约见 [05-bundle-plugins.md](05-bundle-plugins.md)；本文件聚焦 Node half（Cordis entry）与 skill/MCP 声明。

## 仓库布局

插件是 npm 包，**包根 = 仓库根**（无需 `.dsh-plugin` 之类的子目录）：

```
my-plugin/
├── package.json            # name/version + main/exports + dsh.*
├── cordis.patch.yml        # dsh.bundle.patch 指向的组合层（insert 挂载自身）
├── index.mjs               # Node half 入口：完整 Cordis 插件（main/exports["."]）
├── client/  lib/client.js  # client bundle 源码 / 构建产物（dsh.client 通道）
├── skills/                 # agent skills（SKILL.md 文件树，可选）
├── mcp/                    # MCP server 逻辑（stdio，可选）
└── scripts/                # 门禁与生成器（可选）
```

## package.json——dsh 字段契约

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "type": "module",
  "main": "./index.mjs",
  "exports": {
    ".": "./index.mjs",
    "./client": "./lib/client.js",
    "./cordis.patch.yml": "./cordis.patch.yml",
    "./package.json": "./package.json"
  },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" },
    "client": { "platform": "web" }
  }
}
```

- **`dsh.bundle.patch`**：`string | string[]`——指向 `cordis.patch.yml`（组合层，含 `- insert: - id: <自身> name: <包名>`），或一组按序拼接的 patch 文件；声明即 bundle，进 profile 层栈（数组形态官方 web-app 用它同时分发宿主行与 4 个 agent preset，见 [02-profile-and-preset.md](02-profile-and-preset.md)）
- **`dsh.client`**：`platform: web`——client-modules 只扫描声明它的包（无声明不进 `__DSH_BOOT__`）。其余字段：`inject`（消费的其他 client 模块）、`external`（本行消费的 client 包，用于排模块图顺序；**不得声明自己**）。client 包 extends `tsconfig.base.client.json` 并用共享 tsdown preset（`packages/client/tsdown.client.ts`）
- **`exports["./client"]`**：client bundle 路径（`__ModuleLoader__.load` 注册的构建产物）
- **`main`/`exports["."]`**：指向 Cordis entry（`name`/`inject`/`apply`）
- **`icon`（顶层）**：SVG / PNG / JPEG / WebP，**≤ 256 KiB**，路径相对 manifest，realpath 后必须仍在包内——Plugins 页标识（绘制要求见 [SKILL.md](../SKILL.md) Step 2b）
- **`dsh.manifestVersion`**：可选，当前唯一值是 `1`（与 npm 包版本、Session 格式版本无关）
- **`dsh.client.immediately`**：可选布尔——置 true 进入 boot 第一阶段的注册栅栏（缺省随共享应用批次）；一般插件不要设
- **`inject` 声明 `ctx.get` 用到的全部服务**（`settings`/`webServer` 等）——cordis 严格注入，未声明即抛错
- 纯 cordis 插件（无 `dsh.bundle`）可省 `cordis.patch.yml`——经 profile insert 行挂载

### dsh.skills（skill 包）

`SKILL.md` 文件放 `skills/<name>/`，在 `dsh.skills` 声明（相对包根路径）：

```json
"dsh": { "skills": ["./skills/foo/SKILL.md", "./skills/bar/SKILL.md"] }
```

**实测事实（0.1.2-rc.1 / 0.1.5-rc.2 / 0.2.1-rc.1 三版均核实）**：`dsh.skills` **没有任何消费方**——声明它不会注册 skill。skill 的实际发现路径是**文件系统根**（`<项目>/.dsh/skills`、`<项目>/.agents/skills`、`$DSH_HOME/skills`、`~/.agents/skills`，外加 custom 与 bundled 两类）。核实某基线是否已支持，用一次全量搜（零命中 = 未支持）：

```sh
grep -rln "dsh\.skills" <dsh 安装>/node_modules/@deepseek-ai/ | head
```

**分发动作**：随包分发靠**复制或链接 `skills/<name>/` 进发现根**（命令见 [10-install-and-verify.md](10-install-and-verify.md)「随包分发 skill」）；`dsh.skills` 声明可保留作前向声明（不做严格校验，无害），但安装说明**不能**只靠它。

**SKILL.md 写法**（make-skill 规范）：frontmatter（`name` 1-64 小写连字符、`description` 祈使句「Use this skill when...」、可选 `metadata`/`requires`）+ 正文结构（Tool Wrapper / Generator / Reviewer / Inversion / Pipeline 模式），<500 行，细节 progressive disclosure 到 `references/`。仓库 README 用表格列 skill。

### MCP server

**MCP 不是包 manifest 字段**——不存在 `dsh.mcpServers`（0.1.5-rc.2 全仓 `ts`/`json`/`md` 零命中；0.2.1-rc.1 复核：仅 `dsh-acp` 的协议类型里出现 `mcpServers`，不是 manifest 字段）。现行可用形态：CLI 随附 **`@deepseek-ai/dsh-mcp-client`**，由 **patch 层的行**逐台配置服务器，把外部 MCP 工具桥接进 `ctx.tools`（名称形如 `mcp__<server>__<tool>`）；**默认不启用任何服务器**，且只桥接工具（资源与提示词不支持）。每条服务器命令都是 agent 沙箱之外的受信任可执行代码，因此由用户显式开启。

另注：Session／SDK 层确有 `mcpServers` 参数，但**非空值未实现**（会话桥以"扩大 workspace scope"为由拒绝）。配置字段以 `packages/mcp/mcp-client/README.md` 与 CLI 行为参考为准。

## Node half——Cordis entry

```js
import { defineTool } from '@deepseek-ai/dsh-tools'
import z from '@deepseek-ai/schemastery'

export const name = 'my-plugin'
export const inject = ['webServer', 'tools']
/** 可选：声明设置面——条目 id 即设置命名空间；live 字段标 .volatile()。 */
export const Config = z.object({ myFlag: z.boolean().default(true).volatile() })
export function apply(ctx, config) {
  ctx.tools.register(defineTool({
    name: 'my_tool',
    description: 'What it does.',
    parameters: { type: 'object', properties: {} },
    output: { schema: { type: 'string' } },
    execute: async () => 'result',
  }))
}
```

- 能力上限是完整 Cordis——事件（`ctx.on`）、服务（`ctx.provide`）、命令、system prompt、TUI，无需声明。
- **依赖解析**：entry 可 import 官方包（`@deepseek-ai/*`、`cordis`），官方运行时经 profile pnpm 闭包注入（`$DSH_HOME/profiles/node_modules` 扁平 fallback）；**`dependencies`/`peerDependencies`/`devDependencies` 三处都留空**——官方包虽在公共 npm 可见，但自带整条 peer 闭包，单独安装一定失败（细节与本地 link 配方见 [13-gotchas.md](13-gotchas.md) 1）。解析可达性依赖安装位置（profile 树内可达），见 [13-gotchas.md](13-gotchas.md) 6。
- **注册是 effect**：`ctx.tools.register` 返回 disposer，用 `ctx.effect()`/`ctx.on()` 持有生命周期，disable 时清理。
- **必须命名导出**：`name` / `inject` / `apply`（以及 `Config`）要挂在**命名导出**上，不要写成
  `export default { name, inject, apply }`——loader 的 `unwrapExports` 会取 `exports.default`
  并丢掉同一模块上的命名导出，于是 `Config` 读不到（`--dump-config-schema` 里该条目
  `status: "absent"`），设置命名空间永不服务，且**没有任何报错**。
- **设置面靠 `Config` 导出**（可选）：只有导出 schema 的条目才有设置命名空间（= 条目 id），
  live 字段标 `.volatile()`（宿主原地提交新值、不重挂载，并发 `loader/volatile-update`）；
  插件读值走 `apply(ctx, config)` 的第二个参数。客户端把配置页注册进 Plugins 页的槽——
  完整配方（槽选择、读写语义、验证步骤）见 [07-settings-panel.md](07-settings-panel.md)。

## client half（可选）——自渲染

带 UI 的插件声明 `dsh.client` + `exports["./client"]`，client bundle 经 `__ModuleLoader__.load({id, factory})` 注册（factory 返回 `{name, apply}`，由 client 内核挂载时调用 `apply(ctx)`）。自渲染 DOM 逻辑放 `apply` 内——**与填官方 hole 正交**（自渲染跑 bundle 照常，参考实现 `vlln/whale-girl`）。

构建：esbuild CJS 输出 + 外层 `window.__ModuleLoader__.load` 包装（对齐官方 client bundle 产物的包装形态）。

## 持久化：插件状态放哪

**两条路，先选再写**（0.2.1-rc.1 实测）：

**A. 官方 `ctx.storageDomain`（schema 校验、变更事件、host-only）**

web 组合默认已挂 `storage` / `storage-json` / `storage-domain` 三行，json 后端的根是
`$DSH_HOME/storages`（`--dump-config` 里可见 `root: dshHomePath('storages')`）。

```js
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain'
export const ledger = defineDomain({
  name: 'my-plugin-ledger',      // 全局命名空间：加插件前缀，别用通用词
  version: 1,
  tables: { scans: domainTable(scanSchema) },   // 记录 schema 用 @deepseek-ai/schemastery 的 z
})
export const inject = ['storageDomain']
export function apply(ctx) {
  ctx.effect(() => {
    const handle = ctx.storageDomain.open(ledger)   // 异步；句柄归调用方
    handle.table('scans').put(id, record)            // 读同步、写 durable 后返回
    return () => handle.close()
  }, 'my-plugin: ledger')
}
```

- **不是按插件自动隔离**：domain 名是全局的，插件要自己加前缀；同名会撞。
- 记录在 open 时按 schema 校验；版本不匹配直接 `version-mismatch`（无迁移）。
- 只给宿主代码用（模型不可见）；没有 storage 行的组合要先补行。

**B. 每插件数据目录（单文件状态最省事）**

`process.env.DSH_HOME` 下的 `data/<插件 id>/`，例如
`$DSH_HOME/data/dsh-disk-canvas/ledger.json`。写盘用同目录 `.tmp` + `rename` 原子替换，
按体积/条数设上限，`ctx.effect` 的 disposer 里做末次落盘。参考实现 `vlln/whale-girl`
（`$DSH_HOME/data/whale-girl/state.json`）。

- 这个目录**不是 API 保证的隔离**，只是社区/官方示例都在用的约定：按插件 id 命名即互不覆盖。
- **不要**写进插件安装目录或 profile：更新/卸载会把状态一起带走；profile 里的
  `lib/` 与 `node_modules/` 也不是数据区。
- 卸载不会自动删 `data/<id>/`——要么接受残留，要么在 README 写明清理方式。

**判据**：多条记录、需要 schema 校验或变更订阅 → A；一份文档、几十 KB、自己管版本 → B。
只存用户偏好这类小值，优先走条目 `Config`（设置面），不要另起存储。

## 安装与验证

见 [10-install-and-verify.md](10-install-and-verify.md)（区分安装通道与热更新能力，按改动面验证生效）与 [05-bundle-plugins.md](05-bundle-plugins.md)。

## 开发规范

门禁、决策记录、生成物、兼容性标注与协作约束统一见 [09-dev-conventions.md](09-dev-conventions.md)——本文件不重复。
