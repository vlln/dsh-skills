#!/usr/bin/env node
/**
 * verify-session.mjs — read one DSH session log with the harness's OWN
 * persistence code and report whether the GUI can load it.
 *
 * `check-session.py` approximates the harness's checks; this script is the real
 * thing: it imports the installed
 * `@deepseek-ai/dsh-session-persistence-jsonl` (the same module the web server
 * loads), runs the full released-format migration (v0 -> current), and reports
 * the refusal verbatim when the log is rejected.
 *
 * The log is COPIED into a throwaway store first, so nothing under
 * `~/.dsh/sessions` is read-modified or migrated: the harness publishes
 * migrated generations next to the source artifact on a successful open, and we
 * must not trigger that for a file we are only inspecting.
 *
 * usage:
 *   node verify-session.mjs <session.jsonl.zstd> [more.zstd ...]
 *
 * Exit codes: 0 = every log loads, 1 = at least one is refused, 2 = usage or
 * environment error (dsh installation not found).
 *
 * Set DSH_MODULES to the node_modules directory that holds `@deepseek-ai/dsh*`
 * when auto-detection fails (e.g. DSH_MODULES=$(npm root -g)).
 */
import { execFileSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, realpathSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
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
  console.error('verify-session: could not locate the installed dsh packages; set DSH_MODULES=<node_modules dir>')
  process.exit(2)
}

const MODULES = modulesRoot()
const { Context } = await import(pathToFileURL(join(MODULES, '@deepseek-ai/cordis/lib/index.js')).href)
const { default: JsonlSessionPersistence } =
  await import(pathToFileURL(join(MODULES, '@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js')).href)

/** Read only the header line (its own zstd frame) for id/cwd. */
function readHeader(path) {
  const out = execFileSync('zstd', ['-dc', '-q', path], { maxBuffer: 64 * 1024 * 1024 })
  const line = out.toString('utf8').split('\n', 1)[0]
  return JSON.parse(line)
}

/**
 * The backend resolves a stored log from the header alone
 * (`<root>/<projectKey(cwd)>/<encodeSegment(id)>/session.jsonl.zstd`) and
 * refuses a file parked anywhere else, so the copy must reproduce both
 * encodings exactly — ported verbatim from the installed bundle
 * (`session-persistence-jsonl/lib/index.js`, `encodeSegment`/`projectKey`).
 */
function encodeSegment(raw) {
  if (raw === '.') return '~002E'
  if (raw === '..') return '~002E~002E'
  let out = ''
  for (let i = 0; i < raw.length; i++) {
    const code = raw.charCodeAt(i)
    const ch = String.fromCharCode(code)
    if (ch !== '~' && /^[A-Za-z0-9._-]$/.test(ch)) out += ch
    else out += '~' + code.toString(16).toUpperCase().padStart(4, '0')
  }
  return out
}

function projectKey(cwd) {
  if (cwd.length === 0) throw new Error('cannot encode an empty project path')
  let readable = ''
  let separatorRun = false
  for (let i = 0; i < cwd.length; i++) {
    const code = cwd.charCodeAt(i)
    const ch = String.fromCharCode(code)
    if (ch === '/' || ch === '\\' || ch === ':') {
      if (!separatorRun) readable += '-'
      separatorRun = true
    } else if (ch !== '~' && /^[A-Za-z0-9._-]$/.test(ch)) {
      readable += ch
      separatorRun = false
    } else {
      readable += '~' + code.toString(16).toUpperCase().padStart(4, '0')
      separatorRun = false
    }
  }
  return `--${(readable.replace(/^-+/, '') || 'root').slice(0, 251)}--`
}

function summariseTurns(events) {
  const turns = []
  for (const event of events) {
    if (event.type === 'turn/start') turns.push({ turn: event.data.turn, end: undefined })
    else if (event.type === 'turn/end') {
      const current = turns.at(-1)
      if (current !== undefined && current.turn === event.data.turn) current.end = event.data.reason?.kind
    }
  }
  const open = turns.filter(turn => turn.end === undefined)
  return { turns, open }
}

async function verifyOne(path) {
  const header = readHeader(path)
  // One throwaway store per log: two copies of the same session (e.g. a log and
  // its backup) in one root would collide as a duplicate id.
  const root = mkdtempSync(join(process.env.TMPDIR ?? '/tmp', 'dsh-verify-'))
  const target = join(root, projectKey(header.cwd ?? ''), encodeSegment(header.id))
  mkdirSync(target, { recursive: true })
  copyFileSync(path, join(target, 'session.jsonl.zstd'))

  const ctx = new Context()
  const persistence = new JsonlSessionPersistence(ctx, { root, compression: 'zstd' })
  const handle = await persistence.open(header.id, 'read')
  try {
    const read = await handle.read(0, undefined)
    const { turns, open } = summariseTurns(read.events)
    const closers = turns.filter(turn => turn.end === 'interrupted').map(turn => turn.turn)
    console.log(`${path}: OK — ${read.events.length} logical events, ${turns.length} turn(s)`
      + (closers.length ? `, interrupted closer(s) for turn(s) ${closers.join(', ')}` : ''))
    if (open.length) console.log(`${path}:   WARNING: turn(s) ${open.map(t => t.turn).join(', ')} still open in the migrated output`)
    const bad = turns.filter(turn => turn.end === undefined || turn.end === 'error')
    return bad.length === 0
  } finally {
    await handle.close()
    rmSync(root, { recursive: true, force: true })
  }
}

const files = process.argv.slice(2)
if (files.length === 0) {
  console.error('usage: node verify-session.mjs <session.jsonl.zstd> [more.zstd ...]')
  process.exit(2)
}
let ok = true
for (const file of files) {
  if (!existsSync(file)) {
    console.log(`${file}: MISSING`)
    ok = false
    continue
  }
  try {
    if (!await verifyOne(file)) ok = false
  } catch (error) {
    console.log(`${file}: REFUSED — ${error?.constructor?.name ?? 'Error'}: ${error?.message ?? error}`)
    ok = false
  }
}
process.exit(ok ? 0 : 1)
