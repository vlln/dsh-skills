# 从成熟插件提炼工程模式

**来源**：下列钉 commit 的插件实现与历史文档，以及本 skill 的工程约定；短摘录与远程出处见末节。
这些是能力提炼样本，不是官方契约，也不证明所有插件由本 skill 生成、脚本全部完善或本次测试通过。

> **本文件回答**：如何识别可复用实践、选择源码分发或构建、按改动面组合最低门禁。
> **不回答**：插件分发形态与入口字段（→ [04](04-plugin-contract.md)）、依赖解析（→ [05](05-bundle-plugins.md)）、纪律（→ [09](09-dev-conventions.md)）、安装与实例操作（→ [10](10-install-and-verify.md)）。

## 1. 先识别成熟实现，再决定抽取什么

1. 先读目标插件的 manifest、入口、构建与门禁入口，再看测试断言、失败样例和真实宿主证据；不要只看 README 或脚本名。
2. 将需求映射到已有能力：包契约、模块装载、字典审计、产物新鲜度、真实交互、状态持久化、生命周期清理。
3. 区分稳定契约与仓库偶然性：包名、目录、业务状态机、测试账号和运行器路径不能直接变成通用默认。
4. **只提炼能力，不整仓复制**。复用实际代码时核对许可证并记来源；不要调用用户本机兄弟仓库的脚本或假定它们存在。
5. 历史文档可能有漂移；代码存在不等于被执行，脚本通过不等于覆盖真功能，旧记录也不等于当前基线仍成立。

## 2. 分发与构建：两条工程路径，一层风险增强

这不是 bundle / 纯 Cordis 的另一套分类；分发形态仍按 [04](04-plugin-contract.md) 选择。

| 路径 / 叠加层 | 何时采用 | 提炼的能力 |
|---|---|---|
| 直接分发 JS（如 autofork / video2text） | 原生 `.mjs` / `.js` 已满足入口契约，无需转译或资源编译 | 源码即可入包；检查语法、入口、manifest、pack 与真实装载，不凭空增加构建步骤 |
| 有构建（share-link） | TypeScript、JSX、资源处理或多入口输出需要生成物 | Host ESM + client CJS factory；显式 external；入口、输出与 exports 一一对应 |
| 高风险真实宿主回归增强（motion / autofork） | 改会话切换、事件时序、持久化、跨面板写入或复杂状态机 | 在前两条任一路径上叠加真实宿主场景、落盘证据、负控与清理断言；**不是第三种分发形态** |

### 直接分发 JS

- 不把所有 JS 文件一律当生成物；只有存在构建来源的文件才需要新鲜度校验。
- 不因没有构建就免除包契约、国际化、真实安装与真功能调用；业务门禁可检查字典外硬编码并用非法样例自证。
- 工具、命令、面板要验证各自真实入口；不能把“函数可 import”或 mock 注册成功当作激活证据。

### 有构建：Host 与 client 必须分开

- Host 使用 Node ESM；client 使用浏览器 CJS 输出并包入 `window.__ModuleLoader__.load({ id, factory })`，factory 返回模块导出。
- client 的 factory 接收宿主模块装载环境，不能只把裸 CJS 文件交给浏览器，也不能把宿主 SDK / React 再捆一份。
- 按实际 import 将宿主共享模块 external；构建 external 与 manifest 的 `dsh.client.external` 职责不同，须分别核对，后者不得自引包名。
- 多个 Host 子入口必须逐个映射源码、输出和 exports；client 注册 id 与包名同源，避免改名后仍注册到旧 id。
- runtime SDK 由宿主提供；编译与类型验证需要的 SDK / 工具可放 `devDependencies`，但不得因此把宿主 runtime 打进产物。
- runtime 解析、开发依赖与 peer 兼容门槛是不同问题，详细规则归 [05](05-bundle-plugins.md)；不能推导成依赖三字段全空或安装必然 ERESOLVE。

**接入自带构建模板**（仅当项目确实有构建时）：

1. 先读本 skill 的 [tsdown.config.mjs](../templates/tsdown.config.mjs)，理解 Host / client 两段配置；无构建项目不要复制。
2. 将模板复制到**目标 npm 包根**，不是随手放仓库根；按目标包调整 `entry`、`outDir` 与 manifest 的 `exports` / `main`。
3. 包名由模板自动读取目标 manifest，不另维护硬编码副本；按实际 client imports 调整 external，删除不用的入口。
4. 在目标包中配置并执行构建与验证；模板不依赖兄弟仓库脚本。多入口共享输出目录时核对清理策略，避免一次构建删掉另一入口。
5. 重建后检查所有声明出口和实际 pack 内容，再安装该产物；不能用工作树里的旧产物代替发布物验证。

第三方 starter 仅作结构参考；不默认引入 Tailwind、h3 或安装 skills 的 `postinstall`。
这些会增加样式、服务与安装时执行代码的边界，只有需求成立且显式确认后才采用。

## 3. 最低门禁按改动面叠加

按下表取适用项；“所有插件”是基线，其余是叠加，不是用 typecheck / 单测替代真实宿主。

| 改动面 | 最低证据 |
|---|---|
| 所有代码插件 | 所有声明入口与 manifest / patch / exports 对齐；实际 pack 检查资源完整；安装实际分发物，确认条目激活，并经真实入口调用一次核心功能 |
| 存在构建或生成物 | 重新构建并检查产物新鲜度、模块格式、external 与所有输出；无构建路径不强加新鲜度门禁 |
| 存在 TypeScript | 在匹配的开发 SDK 上运行 typecheck；纯 JS 不机械要求 TS typecheck，构建成功也不等于类型检查成功 |
| UI / 样式 / 文案 | 真实点击、输入、导航、错误与空态；浅 / 深主题；zh / en 切换与键覆盖；检查实际样式命中，不只看 DOM 或 HTTP 200 |
| 生命周期 / 注册 / 副作用 | 启停、卸载、重装后真调用；断言监听器、定时器、路由、DOM / style、任务与连接被清理，且不重复注册 |
| 会话 / 持久化 / 并发等高风险行为 | 真实宿主中执行关键序列，核对页面结果与落盘状态；补竞态、重启恢复、负控和必要的跨版本回归 |
| 门禁实现自身 | 用故意损坏的最小 fixture 证明检查会失败；避免只断言“脚本退出 0”而不核对业务结果 |

**CI 中声明强制的 E2E 必须真正执行**：运行器、浏览器、SDK 或 fixture 依赖缺失应非零失败，不能静默 skip 后全绿。
本地可选检查若无法执行，明确记为“未运行”；语法检查不得命名或汇报成完整 E2E。

凭据与外网依赖优先用本地 fixture / mock adapter 替代，不读写真实凭据，不接管用户主 GUI。
真实宿主仍须承载安装、注入、模块装载与交互；mock adapter 只替代外部服务，不能冒充真实宿主。
报告明确哪些端到端链路是真实的、哪些外部边界被替换；外网 / 真实账号兼容性未测就是未测。

## 4. 两种验证实例，各有用途

- **自动回归**：临时隔离 `DSH_HOME` + 随机端口，测试自建、自停、自清理，便于并行与重复运行。
- **手动验收 / 持续调试**：持久私有 home + 固定端口，保留用户测试上下文；不可悄悄换端口、删 home 或在用户测试中重启。
- 两者都不复用共享真实 home；独立进程不等于独立数据。固定端口也不代表启动 token 永远不变。
- 具体创建、启动、交接、端口归属与清理操作只维护在 [10](10-install-and-verify.md)；这里不再复制启动脚本。

## 5. 证据分层，避免把历史变成承诺

| 层次 | 能说明什么 | 不能推出什么 |
|---|---|---|
| 实现 | 某 commit 存在某个检查 / 场景及其断言 | 该检查已执行、无缺陷或已覆盖所有风险 |
| 历史记录 | 某时某基线曾记录过结果或操作方式 | 本次运行成功，或旧说明与现实现一致 |
| 本次实跑 | 本次命令、宿主基线、安装产物、退出状态与观察到的业务结果 | 用户已验收、未测宿主或外部服务也兼容 |
| 人工验收 | 用户在交接实例亲测并确认指定测试点 | 自动门禁覆盖完整、所有场景均无问题 |

交付分别标注“已实现 / 有历史记录 / 本次已运行或未运行 / 待人工确认”，附适用基线和证据位置。
不要把下列源码摘录当作本次测试报告，也不要由样本推出所有插件都使用同一工程栈。

## 6. 钉 commit 的来源与短摘录

- [vlln/dsh-share-link@c4e22e979ffdd2f6535670daa41f19480ea94daa：tsdown.config.ts](https://github.com/vlln/dsh-share-link/blob/c4e22e979ffdd2f6535670daa41f19480ea94daa/tsdown.config.ts#L1)：摘录“Node（esm）+ 官方 client bundle（cjs，__ModuleLoader__ 契约）”；提炼双 half 构建与多入口映射。
- [同一 share-link 配置：external](https://github.com/vlln/dsh-share-link/blob/c4e22e979ffdd2f6535670daa41f19480ea94daa/tsdown.config.ts#L19)：摘录 `external: [/@deepseek-ai\//],`；提炼宿主模块外置，不照搬业务入口。
- [vlln/dsh-motion@9a01fd9：gate-client.mjs](https://github.com/vlln/dsh-motion/blob/9a01fd9/scripts/gate-client.mjs#L88)：摘录“a panel write lands in the workspace timeline”；提炼真实交互后的业务结果断言。
- [同一 motion commit：gate-bundle.mjs](https://github.com/vlln/dsh-motion/blob/9a01fd9/scripts/gate-bundle.mjs#L56)：摘录“the panel bundle is up to date”；提炼生成物新鲜度，不推广给无构建项目。
- [同一 motion commit：verify-standalone.mjs](https://github.com/vlln/dsh-motion/blob/9a01fd9/scripts/verify-standalone.mjs#L30)：摘录“Structurally refuse the shared home”；提炼私有实例的结构性保护，不复制其整套启动实现。
- [vlln/dsh-autofork@6c7f83c：gate.test.mjs](https://github.com/vlln/dsh-autofork/blob/6c7f83c/tests/gate.test.mjs#L79)：摘录“hardcoded UI copy outside the dictionary is rejected”；提炼字典审计与拒绝坏样例的自证测试。
- [同一 autofork commit：E2E README](https://github.com/vlln/dsh-autofork/blob/6c7f83c/tests/e2e/README.md#L4)：摘录“在真实 harness 上跑完整场景，然后从落盘的会话日志里读证据。”；提炼真实宿主与持久化证据。
- [同一 E2E README：检查边界](https://github.com/vlln/dsh-autofork/blob/6c7f83c/tests/e2e/README.md#L24)：摘录“只做这一层脚本的语法检查”；该历史说明将场景留给手工跑，不能宣称其已是 CI 强制自动 E2E。
