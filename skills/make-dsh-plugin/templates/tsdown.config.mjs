// 双端构建模板（不是已验证的插件）：只在项目确需编译时适配。
// 原创提炼的通用配置；参考能力来源见 ../references/16-engineering-patterns.md。
// 从插件包根运行 tsdown --config tsdown.config.mjs；不要从 skill 根构建。
// 先改 entry/outDir，再对齐 manifest main/exports/files；包名从目标 manifest 取。
// 多工具入口加到 host entry；纯 Host 可删除 client 配置。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const manifest = JSON.parse(readFileSync(resolve('package.json'), 'utf8'))
if (typeof manifest.name !== 'string' || !manifest.name.trim()) {
  throw new Error('Build from a plugin package root with a non-empty package name')
}
const id = JSON.stringify(manifest.name)
const external = [
  /^@deepseek-ai\//,
  'cordis',
  'react',
  'react/jsx-runtime',
  'react/jsx-dev-runtime',
  'react-dom',
  'react-dom/client',
]

export default [
  {
    entry: { index: 'src/index.mjs' },
    outDir: 'lib',
    format: 'esm',
    platform: 'node',
    target: 'es2022',
    outExtensions: () => ({ js: '.mjs' }),
    external,
    dts: false,
    clean: true,
  },
  {
    // JS 项目可换成 src/client/index.js；TS 另跑 tsc --noEmit。
    entry: { client: 'src/client/index.ts' },
    outDir: 'lib',
    format: 'cjs',
    platform: 'browser',
    target: 'es2022',
    outExtensions: () => ({ js: '.js' }),
    external,
    dts: false,
    clean: false,
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    // CJS 的 exports 留在 factory 里；不能只输出裸 CJS/ESM。
    banner: `window.__ModuleLoader__.load({id:${id},factory:(require)=>{var module={exports:{}};var exports=module.exports;`,
    footer: 'return module.exports;}});',
  },
]
