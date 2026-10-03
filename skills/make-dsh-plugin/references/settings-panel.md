# 官方设置面集成（条目 Config + plugins.bundle.config）

第三方插件把自己参数的配置页挂进**侧边栏 Plugins 页**的方法——注意**不是**「设置 → 插件」：
那里现在是**只读的插件清单**（`dsh-client-ui-settings-plugin-inventory` 的 Plugin list tab，
外壳是 `dsh-client-ui-settings-plugins` 的 `settings.plugins.tab` 槽，不提供配置写入）。
基线 **0.2.0-rc.2**
（实测参考实现：`vlln/whale-girl` 的配置卡片）。分两个 half：Node half 用**条目
`Config` schema** 声明设置命名空间；client half 把配置页注册进 **Plugins 页的槽**。

> 官方文档覆盖同一主题（[adding-a-settings-card.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-settings-card.md)）。
> 与官方冲突时以官方为准；本文件保留的是实测细节与踩坑。

## 1. 契约锚点（0.2.0-rc.2 实测）

- **设置命名空间 = 导出 `Config` schema 的条目 id`**。插件不再自行注册命名空间名字；
  宿主 `dsh-settings` 的 `describe()` 会跳过没有 `Config` 的条目——没导出它就等于
  「这个插件没有设置面」（配置页不出现、旧 `settings.yaml` section 不被读取）。
- **配置入口在侧边栏 Plugins 页，不在 Settings**。Settings → 插件 是**只读清单**（inspect only，
  连官方自己的插件页都不放在那儿）；写入面只有插件包页/行页上注册的配置卡片。
- **`autoGenerate` 不是自动设置页**：设置描述符里带这个布尔（语义是「没有自定义页时是否允许生成页面」），
  但 shipped web UI 里**没有消费方**（实测：全仓只在设置管线与线上 codec 之间传递）——所以
  **只声明 `Config` 不会长出任何界面**。要 UI 就必须注册卡片；否则用户只能手改 profile patch 里的
  `config:`（手写 YAML，等于没有 GUI 配置面）。
- **四处同名**（实测：任一处漂移即卡片静默消失）：
  `cordis.patch.yml` 的 insert 条目 id、`package.json` 的包名、Node half 的命名空间常量、
  client half 的命名空间字面量。宿主用**条目 id** 作命名空间、用**包名**作
  `plugins.bundle.config` 的 key。
- **live 字段靠 `.volatile()`**：schema 上标了 volatile 的**叶**被宿主换成实时引用
  （`createVolatile` → 冻结对象 `{ get() }`，可以嵌在普通对象/数组里）。改值由宿主原地
  提交进运行中的 fiber、**不重挂载**，随后发 `loader/volatile-update(paths)`。
  volatile 只影响「是否重挂载」，**值照样落进 profile patch**（持久）。
- **只有叶能标 volatile**：容器标了会让「写整组」这一路径不被认（`isVolatilePath` 逐段
  下行）；叶标 volatile 才能写深路径 `['walk','enabled']`——两半唯一自洽的组合。
- **`.volatile()` 只在 `@deepseek-ai/schemastery`**（dsh 的 fork）里；公共 npm 的
  `schemastery` 没有这个方法，且只有 fork 的 `~standard.validate()` 会把 volatile 叶
  换成引用。插件的 `Config` 必须用 fork 构建。
- 客户端注入面：`slots`（槽注册）、`locale`（文案）、`configForms`（配置读写传输）。
  **`settingsScope` / `settings.plugin.item` 已退役**——注入了宿主不存在的服务会让整个
  client 条目永久 pending（见 [gotchas.md](gotchas.md) §9）。

## 2. Node half：`Config` schema + 读值

```js
import z from '@deepseek-ai/schemastery'        // fork：.volatile() 与引用式校验在这里

export const NAMESPACE = 'my-plugin'            // = 条目 id = 包名（四处同名）
export const DEFAULTS = Object.freeze({ myTool: true, size: 110 })
export function buildSchema() {
  return z.object({
    myTool: z.boolean().default(DEFAULTS.myTool).volatile(),
    size: z.number().min(64).max(160).default(DEFAULTS.size).volatile(),
    walk: z.object({ enabled: z.boolean().default(true).volatile() }),  // 容器保持普通对象
  })
}
export const Config = buildSchema()             // ← 命名空间由此存在

export function apply(ctx, config) {
  let cfg = readConfig(config)                  // 解引用 + DEFAULTS 补缺
  ctx.effect(() => ctx.on('loader/volatile-update', () => {
    cfg = readConfig(config)                    // 配置变化后重读；要热更新客户端就递增
    configRevision += 1                         // 自己的 revision 并下发（/state 门控）
  }), 'my-plugin: config')
}

/** volatile 叶 → 普通值；顺带与 DEFAULTS 合并补缺。 */
function readConfig(config) {
  const unwrap = (v) => (v !== null && typeof v === 'object' && typeof v.get === 'function'
    && Object.keys(v).length === 1 ? unwrap(v.get())
    : Array.isArray(v) ? v.map(unwrap)
    : v !== null && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, unwrap(x)]))
    : v)
  return { ...DEFAULTS, ...unwrap(config ?? {}) }
}
```

要点：

- **读值必须走 `config`**：`apply(ctx, config)` 的第二个参数就是宿主校验后的条目配置，
  volatile 叶是引用；**别缓存引用本身**（引用稳定、值会变），每次要用就 `.get()` 或重读快照。
- **schema 承担单字段约束**（min/max/default）；跨字段校验没有写时钩子（schema 上没有
  `custom()`/`validate()`），要在读值时归一化（如成对区间 min>max 交换）。
- `inject` **不要**再声明 `settings`：那个服务在 0.2.0 已被 `SettingsForms`
  （`describe/update/replace/mutate`）取代，插件侧不再需要它。
- 配置页只在宿主服务该命名空间时出现——客户端用 `configForms.whileServed([ns], …)` 把注册
  挂上去，别自己判断。
- 旧 `<dshHome>/settings.yaml` 的 `<ns>:` section 由宿主的 legacy 导入**一次性**搬进条目
  config（同一次导入还会重命名 settings.yaml）；此后的活文档是 profile patch。

## 3. Client half：注册配置页

```js
export const inject = ['slots', 'locale', 'configForms']
export function apply(ctx) {
  const t = ctx.locale.bind(NS)
  ctx.effect(() => ctx.locale.register(NS, { zh, en }), 'my-plugin: copy')
  const scope = ctx.configForms.get(NAMESPACE)   // 官方 ConfigFormController：稳定引用
  const form = new MyForm(scope)                 // 暂存/保存语义见 §4
  ctx.effect(() => () => form.dispose(), 'my-plugin: form')
  ctx.effect(() => ctx.configForms.whileServed([NAMESPACE], () =>
    ctx.slots.inject('plugins.bundle.config', () => ctx.slots.register({
      name: 'plugins.bundle.config',
      key: PKG_NAME,                             // key = **bundle 包名**（= package.json name）
                                                 // 注意：它可能与命名空间/条目 id 不同名——whale-girl 三者同名只是巧合
      locale: NS,
      inject: () => ({ hooks: { myForm: { getSnapshot: form.getSnapshot, subscribe: form.subscribe } }, ...form.actions }),
    }, MyCard))), 'my-plugin: page')
}
```

槽选择（`plugins.*` 三槽由 `dsh-client-ui-plugin-manager` 声明，keyed/list 形态与渲染位置不同）：

| 槽 | key | 渲染位置 | 何时选 |
|---|---|---|---|
| `plugins.bundle.config` | bundle 包名 | 包页上「描述与行清单之间」的配置区，页面只请求 `page` 视图 | 自己的 bundle 自带配置（推荐；实测可用） |
| `plugins.row.config` | `<包名>#<行 id>` | 包页该行的「配置」入口，开独立页 | 按 patch 行分别配置 |
| `plugins.item` | —— （list 槽，用一个 `id`） | Plugins 页「官方」组的卡片 | 官方语义位置，第三方 bundle 不建议占用 |
| `settings.plugins.tab` | —— （list 槽，用一个 `id`） | **Settings → 插件** 那一节里的 tab | 别往这儿挂配置页——官方只在那里放只读清单，插件的配置入口一律在侧边栏 Plugins 页 |

渲染契约：

- 条目组件收到 `{ view: 'summary' | 'page' }` + 自己 `inject` 的 face + `locale` 词典。
  **hooks 要放在视图分支之前**（同一实例两种视图共用同一钩子序列）。
- `summary` 回一句话（卡片/pc 页的 one-liner）；`page` 画字段区与**自己的保存脚注**。
  `plugins.bundle.config` 的 chrome（图标/标题/描述/面包屑）由包页画，组件不要再画卡头。
- 平台种子表 `getStaticModules()` 提供 `react` / `react-dom` / `@deepseek-ai/cordis` /
  `@deepseek-ai/dsh-client-store` / `@deepseek-ai/dsh-client-ui-slots` /
  **`@deepseek-ai/dsh-client-ui-primitives`** / `@deepseek-ai/dsh-client-ui-dockkit`；
  primitives 里有 `Switch`、`Input`、`Tag`、`Modal`、`SettingsForm`、`SettingsValueField`
  等控件（0.2.0 实测：开关不必再自绘）。bundle 里 `require()` 这些 id 即可，esbuild 侧
  按 external 处理，不自带运行时。

## 4. 读写语义（实测）

- scope 快照：`{ status: 'loading'|'ready'|'unavailable', value, base, user, revision, writable, mode }`；
  `value` 是 schema 解析后的当前值，`user` 里有键即「被用户覆盖」。
- 写：`mutate(ops, expectedRevision)` 一次提交多字段，**路径是数组、可任意深**——
  `set(field, value)`/`unset(field)` 只达单段，嵌套字段（`walk.enabled`）用 `mutate`。
  `expectedRevision` 用**用户开始编辑时**读到的 revision（CAS：期间他人写入 → 拒绝）。
- **保存后按宿主接受值重读确认**：逐字段比对；比较要按**结构等价**（宿主往返后数组/对象
  引用必然不同，引用比较会把成功保存误判为失败）。
- **快照引用稳定（React #185 血泪）**：`useSyncExternalStore` 要求内容未变时返回同一对象；
  `getSnapshot` 每次新造对象 → 无限重渲 → 控制台 `Minified React error #185`。
  实测模式：草稿对象每次变更整体替换（引用即失效信号）+ scope 快照引用做缓存键。

## 5. 验证（可复制）

1. **命名空间存在**（Node 侧，无需浏览器）：

   ```sh
   dsh --profile web --dump-config-schema | grep -A3 '"id": "my-plugin"'
   # 期望 status: "schema" 与 configRef；"absent" = 模块没加载，或 entry 用了 export default
   # 把 Config 遮住（loader 的 unwrapExports 只取 default——见 entry-contract.md）
   ```

2. **卡片渲染**（浏览器，headless Chrome CDP）：打开 `Plugins` 页 → 点
   `[data-plugin-package="my-plugin"] button` → 断言
   `document.querySelector('[data-plugin-slot="plugins.bundle.config"] [data-my-card]')` 非空。
   只查「页面没报错」不足：条目 pending 时页面照样干净。

3. **保存真的生效**（三处一致才算）：

   ```sh
   curl -s http://127.0.0.1:<port>/<route-prefix>/config   # 插件自己下发的值
   grep -A6 '^- id: my-plugin' <dshHome>/profiles/web/cordis.patch.yml   # 落进条目 config
   ```

   再回到页面确认插件行为/客户端渲染跟着变（volatile 原地提交，**无页面刷新、无重挂载**）。

4. **负控**：故意把槽名或 inject 服务名写错一次，确认日志/面板会响亮报错（client 条目
   pending 只在 web 启动面板显示），再改回来。
