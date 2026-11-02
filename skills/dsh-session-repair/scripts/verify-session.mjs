#!/usr/bin/env node
/**
 * verify-session.mjs — read one DSH session log with the harness's OWN
 * persistence code and report whether the GUI can load it.
 *
 * `check-session.py` approximates the harness's checks; this script is the real
 * thing: it mounts the installed
 * `@deepseek-ai/dsh-session-persistence-jsonl` on a bare Cordis Context (the
 * same module and the same migration chain the web server loads), points it at
 * a throwaway store holding a COPY of the log, and opens it read-only.
 *
 * The real store is never touched: nothing under `~/.dsh/sessions` is read,
 * migrated, or rewritten (a successful open publishes the migrated generation
 * next to the artifact).
 *
 * usage:
 *   node verify-session.mjs <session.jsonl.zstd> [more.zstd ...]
 *
 * Exit codes: 0 = every log loads, 1 = at least one is refused, 2 = usage or
 * environment error (dsh installation not found, unreadable header).
 *
 * Set DSH_MODULES to the node_modules directory that holds `@deepseek-ai/dsh*`
 * when auto-detection fails (e.g. DSH_MODULES=$(npm root -g)).
 *
 * Baseline note: the previous implementation called `new JsonlSessionPersistence(...)`.
 * The package now exports a Cordis plugin (`apply` / `Config`), so that shape
 * throws `TypeError: JsonlSessionPersistence is not a constructor` on current
 * builds. Mounting the plugin is the version-agnostic route: it needs no
 * private constructor signature, only the service name `sessionPersistence`
 * and the two constructor config fields (`root`, `compression`).
 */
import { execFileSync, spawn } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, realpathSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

function modulesRoot() {
  if (process.env.DSH_MODULES) return resolve(process.env.DSH_MODULES)
  const candidates = []
  // The running dsh CLI: <modules>/@deepseek-ai/dsh/lib/bin.js, whose own
  // dependencies live either beside it or under its bundled node_modules.
  try {
    const bin = realpathSync(execFileSync('/bin/bash', ['-c', 'command -v dsh'], { encoding: 'utf8' }).trim())
    const root = resolve(dirname(bin), '../../..')
    candidates.push(root, join(root, '@deepseek-ai/dsh/node_modules'))
  } catch { /* dsh not on PATH */ }
  const home = process.env.HOME ?? ''
  const globs = [
    join(home, '.local/share/pi-node'),
    join(home, '.nvm/versions/node'),
    join(home, '.local/share/pnpm'),
  ]
  for (const glob of globs) {
    if (!existsSync(glob)) continue
    let entries
    try { entries = readdirSync(glob) } catch { continue }
    for (const entry of entries) {
      for (const root of [join(glob, entry, 'lib/node_modules'), join(glob, entry)]) {
        candidates.push(root, join(root, '@deepseek-ai/dsh/node_modules'))
      }
    }
  }
  candidates.push('/usr/local/lib/node_modules', '/opt/homebrew/lib/node_modules')
  for (const candidate of candidates) {
    if (existsSync(join(candidate, '@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js'))
      && existsSync(join(candidate, '@deepseek-ai/cordis/lib/index.js'))) return candidate
  }
  return undefined
}

/**
 * The project directory the store expects for a cwd — a mirror of `projectKey`
 * in `@deepseek-ai/dsh-session-persistence-jsonl`. The store refuses an artifact
 * whose location does not match its header (`header id … and cwd identify …`),
 * so the throwaway copy must sit under this key.
 */
function projectKey(cwd) {
  if (cwd === undefined) return '_no-cwd'
  let readable = ''
  let separatorRun = false
  for (const ch of cwd) {
    if (ch === '/' || ch === '\\' || ch === ':') {
      if (!separatorRun) readable += '-'
      separatorRun = true
    } else if (ch !== '~' && /^[A-Za-z0-9._-]$/.test(ch)) {
      readable += ch
      separatorRun = false
    } else {
      readable += '~' + ch.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')
      separatorRun = false
    }
  }
  return `--${(readable.replace(/^-+/, '') || 'root').slice(0, 251)}--`
}

/** Read the header line (the only line in the log's first zstd frame). */
function readHeader(path) {
  return new Promise((resolveHeader, reject) => {
    const child = spawn('zstd', ['-dc', '-q', path])
    let buffer = ''
    let done = false
    const finish = (fn, value) => {
      if (done) return
      done = true
      child.kill()
      fn(value)
    }
    child.stdout.on('data', (chunk) => {
      buffer += chunk.toString('utf8')
      const end = buffer.indexOf('\n')
      if (end === -1) return
      try { finish(resolveHeader, JSON.parse(buffer.slice(0, end))) } catch (error) { finish(reject, error) }
    })
    child.on('error', (error) => finish(reject, error))
    child.on('close', () => finish(reject, new Error('session header line not found')))
  })
}

async function waitForService(app, name, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const service = app.get(name)
    if (service) return service
    if (Date.now() > deadline) throw new Error(`service "${name}" did not become available`)
    await new Promise((r) => setTimeout(r, 20))
  }
}

async function verifyOne(path, root) {
  const work = mkdtempSync(join(tmpdir(), 'dsh-verify-'))
  const store = join(work, 'sessions')
  try {
    const header = await readHeader(path)
    const id = header.id
    const dir = join(store, projectKey(header.cwd), id)
    mkdirSync(dir, { recursive: true })
    copyFileSync(path, join(dir, basename(path)))

    const { Context } = await import(pathToFileURL(join(root, '@deepseek-ai/cordis/lib/index.js')).href)
    const { apply } = await import(pathToFileURL(join(root, '@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js')).href)
    const app = new Context()
    app.plugin(apply, { root: store, compression: 'zstd' })
    const persistence = await waitForService(app, 'sessionPersistence')

    const handle = await persistence.open(id, 'read')
    const { events } = await handle.read()
    await handle.close()
    const turns = events.filter((event) => event.type === 'turn/start').length
    const interrupted = events.filter((event) => event.type === 'turn/end' && event.data?.reason?.kind === 'interrupted').length
    return {
      ok: true,
      text: `OK — ${events.length} logical events, ${turns} turn(s)`
        + (interrupted ? `, interrupted closer(s) for ${interrupted} turn(s)` : ''),
    }
  } catch (error) {
    return { ok: false, text: `REFUSED — ${error?.name ?? 'Error'}: ${error?.message ?? error}` }
  } finally {
    rmSync(work, { recursive: true, force: true })
  }
}

async function main() {
  const targets = process.argv.slice(2)
  if (targets.length === 0) {
    console.error('usage: node verify-session.mjs <session.jsonl.zstd> [more.zstd ...]')
    return 2
  }
  const root = modulesRoot()
  if (root === undefined) {
    console.error('cannot locate the installed @deepseek-ai dsh packages; set DSH_MODULES=<node_modules dir>')
    return 2
  }
  let failed = 0
  for (const path of targets) {
    if (!existsSync(path)) {
      console.log(`${path}: ERROR — no such file`)
      failed += 1
      continue
    }
    const result = await verifyOne(resolve(path), root)
    console.log(`${path}: ${result.text}`)
    if (!result.ok) failed += 1
  }
  return failed > 0 ? 1 : 0
}

process.exit(await main())
