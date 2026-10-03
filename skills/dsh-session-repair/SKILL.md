---
name: dsh-session-repair
description: >-
  当 DSH 会话历史在 GUI 中无法加载或显示错乱时使用本技能——例如报错
  "corrupt Zstandard session log: complete frame contains a torn JSONL record"、
  "turn/start N does not close the prior turn"、会话打不开、或对话尾部/顺序错乱。
  两个常见根因：(1) 同一会话被两个客户端同时打开或继续（两个 GUI 标签页、两个 dsh
  进程），第二个写入者从过期水位恢复，追加的事件 seq 与已提交的重复；(2) 回合结构
  损坏——某个 turn 只有 turn/start 没有 turn/end，紧随其后的 turn/start 被 harness
  的格式迁移拒绝。本技能扫描 ~/.dsh/sessions 下的 JSONL 会话日志，检测并修复这两类
  损坏，再用 harness 自身的持久化代码验证修复结果。
license: MIT
metadata:
  author: vlln
  version: "0.2.0"
requires:
  bins:
    - zstd
    - python3
---

# DSH Session Log Repair

Use this skill when a DSH session's history is broken in the GUI. Two
independent defects each make the WHOLE session unloadable, and a log can carry
either one while looking perfectly fine line by line:

| Family | Contract violated | GUI symptom |
|---|---|---|
| **Seq corruption** | The decoded event stream must be strictly contiguous `seq 0,1,…,N`. | `corrupt Zstandard session log: complete frame contains a torn JSONL record`, "history unavailable". |
| **Turn-structure corruption** | At most ONE turn may be open: every `turn/start` must be preceded by the close of the previous turn (a `turn/end`, or the one inbox shape the harness recovers). | `turn/start N does not close the prior turn; source v0 artifact remains unchanged`, `failed to observe session …` |

Seq corruption comes from **concurrent multi-client writes**: two clients (GUI
tabs, or two dsh processes like the `dsh-0806`/`dsh-0807` stations) appended to
the same session log, and the second writer's seq counter was stale, so it
appended events whose seqs repeat values already in the log.

Turn-structure corruption is a **writer defect / lost append**, not a seq
problem: the log's seqs stay contiguous (the seq check reports OK!) while a
turn is left open mid-log. Engine-side, `turn/end` is appended in a `finally`,
so the interrupted turn's closer can go missing when the turn is superseded,
the process is killed mid-turn, or a resumed writer continues the log.

## Why the seq contract rejects the whole log

The persistence scanner (`SessionLogScanner` in
`@deepseek-ai/dsh-session-persistence-jsonl`) requires the decoded event
stream to be **strictly contiguous seq 0,1,2,…,N** — no duplicates, no gaps,
no out-of-order events. One duplicated line freezes the scanner's commit
cursor, so the WHOLE log is rejected:

```
corrupt Zstandard session log: complete frame contains a torn JSONL record
```

## Why the turn contract rejects the whole log

Reading a stored artifact runs the released-format migration chain
(`session-format-v0-to-v1` → `v1-to-v2` → `v2-to-v3`) in front of the current
logical stream. That migration walks turns with a single `openTurn` slot and
refuses the artifact outright when a new `turn/start` arrives while a turn is
still open:

```
turn/start 39 does not close the prior turn;
source v0 artifact remains unchanged (raw log: …/session.jsonl.zstd)
```

`~/.dsh` wraps that as `failed to observe session "…"`, and the session never
opens — even though every seq is contiguous.

**The harness recovers exactly one shape here** (`legacyInterruptedTurnRestart`
in the v0 relationships, then `legacyInterruptedTurn` in the v1→v2 migration):
the *released resume restart*, where the event immediately before the offending
`turn/start` is an `agent/inbox/spliced` insert with `target: "next-turn"` and a
non-empty `inserted`. The harness then synthesizes
`turn/end {turn: <open>, reason: {kind: "interrupted"}}` itself, so such a log
loads normally and must NOT be "repaired" by hand.

Any other shape — the same break after a `next-step` insert (a subagent
message), a lost `turn/end`, a resumed writer — is refused. Real-world
frequency: in one store of 767 sessions, every mid-log open turn but one was the
recoverable `next-turn` variant (and those sessions loaded fine); the single
`next-step` variant was unloadable. Do not assume the recoverable majority means
the unloadable one is fine.

## Two auto-repairable seq classes (A/B)

| Class | Pattern | Fix |
|---|---|---|
| **A — stale tail** | The real content ends cleanly; the stale writer's appended suffix repeats already-committed seqs. | Truncate the log at the first duplicated line. |
| **B — stale counter** | A resumed writer reused ONE old seq (typically duplicating the preceding `session/end-seed`), then continued with NEW ascending seqs. | Shift every event from the duplicated line onward by the offset that restores contiguity (`seq`, packed-row `seq0`, and the reference fields `sourceEventSeqs`/`messageSeqs` shift together). |

Anything else — a **gap** (a seq is missing entirely) or an out-of-order line
whose tail is a mixed pattern — is NOT auto-repairable; the script fails
closed and asks for manual review. It never writes a file it cannot verify.

## The auto-repairable turn-structure class (C)

| Class | Pattern | Fix |
|---|---|---|
| **C — unclosed turn** | A `turn/start` whose open turn never got a `turn/end`, in a shape the harness does NOT recover (see above). | Insert the closers the harness itself synthesizes — `step/end` first when a step is still open inside that turn, then `turn/end {turn, reason:{kind:"interrupted"}}` — immediately BEFORE the offending `turn/start`; renumber every later event by the number of closers inserted before it and push `sourceEventSeqs`/`messageSeqs` through the same mapping. |

Refused (exit 2, manual review): a `turn/end` with no matching open turn, a
`turn/start` that skips a turn number, a pre-release "legacy" log (whose turn
structure the harness normalizes itself), an open turn that starts before the
last `session/end-seed` marker (closing it would move the inherited cut), and an
interrupted turn with an unanswered `tool/call` — closing that one needs a
synthetic tool result (which the harness synthesizes on resume but this skill
will not fabricate).

## Pipeline

### Stage 1: Locate the session log

Sessions live under `~/.dsh/sessions/<project-dir>/<session-id>/session.jsonl.zstd`
(project dirs are URL-encoded cwd paths like `--Users-vlln-Project-dsh-plugins--`).
Find the id from the GUI's workspace, or from
`~/.dsh/storages/workspace.json` (sessionIds per workspace) and
`~/.dsh/storages/session_projcache.json` (session id → title).

### Stage 2: Check

```bash
export _S="$HOME/.agents/skills/dsh-session-repair"
python3 "$_S/scripts/check-session.py" <path/to/session.jsonl.zstd>
```

Or scan the whole store (finds every corrupted session at once):

```bash
python3 "$_S/scripts/check-session.py" --all
```

Exit 0 = all clean; 1 = a violation was found. Both families are checked in one
pass:

- **Seq violations** name the kind (`DUPLICATE` / `GAP` / `OUT-OF-ORDER`), the
  offending seq, the event type, the physical line, and the expected seq. Packed
  chunk rows (`text-chunks`/`reasoning-chunks`/`tool-call-chunks`) carry `seq0`
  (not `seq`) and expand to `seq0..seq0+len-1`; the script handles this, do not
  hand-check raw lines.
- **Turn-structure violations** print `OPEN-TURN … — the harness cannot recover
  it`, plus the preceding event and its `target`, and whether a step is open.
- **Notes** (not violations) explain benign shapes: an open turn the harness
  closes itself (`next-turn` insert), a trailing open turn (normal crash shape,
  closed on resume), or a skipped structural check on a seeded log. `--all
  --quiet-notes` prints only failing files.

### Stage 3: Repair (to a new file first)

Pick the script by the violation Stage 2 reported. **If both are present, fix
the seq family first** — the turn-structure script requires a contiguous seq
stream.

```bash
# seq family (classes A/B)
python3 "$_S/scripts/repair-session.py" <path/to/session.jsonl.zstd> \
  --out /tmp/session.fixed.jsonl.zstd

# turn-structure family (class C)
python3 "$_S/scripts/repair-turn-structure.py" <path/to/session.jsonl.zstd> \
  --out /tmp/session.fixed.jsonl.zstd
```

Exit 0 = repaired; 1 = nothing to repair; 2 = not auto-repairable (read the
message; do not force it). Each output line states what was applied and the
resulting event count/seq range. **Checkpoint: never skip this — both scripts
re-verify their own output (seq contiguity, and for class C the full turn
structure) and refuse to write a file that does not pass.**

### Stage 4: Install and verify through the harness's own reader

```bash
# whichever script Stage 3 selected; both accept the same flags
python3 "$_S/scripts/repair-session.py" <path/to/session.jsonl.zstd> \
  --install --backup-dir <backup-dir>
```

`--install` backs up the original (`<name>.bak-<timestamp>`), replaces the log
(atomically, chmod 600), and prints the backup path.

Then confirm the harness itself can read the result — this is the authoritative
test, because it runs the real migration instead of the skill's approximation:

```bash
node "$_S/scripts/verify-session.mjs" <path/to/session.jsonl.zstd>
```

It copies the log into a throwaway store, opens it read-only with the installed
`@deepseek-ai/dsh-session-persistence-jsonl`, and prints either
`OK — <n> logical events, <t> turn(s), interrupted closer(s) for turn(s) …` or
the refusal verbatim (exit 0/1). It never migrates or rewrites the real
artifact. Set `DSH_MODULES=<node_modules dir>` if it cannot locate the installed
dsh packages.

Finally refresh the GUI and open the session. The projection cache
(`~/.dsh/storages/session_projcache/`) self-heals on the next cold read — do NOT
edit it by hand.

## Gotchas

- **This skill only models TWO contracts.** A log can also be refused for
  reasons outside them — a newer-format event this build does not support
  (`subagent/descriptor … uses unsupported descriptor version N`), or the
  pre-release "legacy" shape (`turn/start` carries a `trigger`), whose turn
  structure the harness normalizes and whose seed boundaries restart turn
  numbering. `check-session.py` detects the legacy shape and reports
  `OK … note: pre-release "legacy" format …` instead of guessing; treat
  `verify-session.mjs` as the authority in both cases, and do not "fix" such a
  log by hand.
- **A clean seq check does NOT mean the session loads.** The turn-structure
  family leaves seqs perfectly contiguous. Always run the full
  `check-session.py` (or `verify-session.mjs`) before concluding a log is fine.
- **Do not "repair" the recoverable restart shape.** An open turn that the
  event immediately before the `turn/start` recovers (a `next-turn` inbox
  insert) is by design; the harness closes it as `interrupted` on read.
  `check-session.py` reports it as a note and `repair-turn-structure.py` leaves
  it alone.
- **Class C closers must sit immediately BEFORE the offending `turn/start`,
  and the whole tail must be renumbered.** An insertion shifts every later
  event; references shift by the same amount — which is **2**, not 1, when the
  interrupted turn also had an open step (`step/end` + `turn/end`). The script
  does this and re-verifies; a hand edit almost always gets the offsets wrong.
- **Never invent events beyond the closers.** If the interrupted turn has an
  unanswered `tool/call`, stop and report it instead of fabricating a
  `tool/result`.
- **One duplicated line kills the whole session.** Do not judge by eye or by
  `zstd -dc | wc -l`; the log can look fine and still be rejected.
- **The header line is special.** The first frame must contain EXACTLY the one
  header line (type `session`); the harness's `list()` reads only that frame.
  Both repair scripts re-encode with the harness's framing — header line in its
  own checksummed zstd frame, events in a body frame, both with
  `zstd --check`. Do not recompress the whole file with plain `zstd` into one
  frame and expect it to work.
- **Class B shift must include references.** After shifting `seq`/`seq0` by the
  offset, also shift `sourceEventSeqs` and `messageSeqs` values that point
  into the shifted region — otherwise compaction markers and titles reference
  stale seqs. The script does this; a manual edit almost always forgets it.
- **Never repair a LIVE session.** If a client still has the session open and
  active, it can append more events and re-corrupt the file right after the
  fix. A held session also has a `session.lock` next to the log; check the
  session's mtime and that file first. Repair, then have the user close other
  tabs/processes holding the session.
- **Interrupted-turn closers are expected.** A `turn/end (interrupted)` is by
  design: the harness synthesizes one for a trailing open turn on resume, and
  class C repair writes the same event for a mid-log open turn. It is not a new
  problem.
- **Do not touch the projection cache or workspace.json.** Both are derived
  state; the cache is fail-soft and heals on cold read.

## Manual review (when repair refuses)

- A `GAP` means an event is missing entirely — the log cannot be made
  contiguous by truncation or shifting. Recover the missing range from another
  source if possible (a live session's in-memory copy, or the parent/fork
  session the events were seeded from), or accept losing the tail.
- An `ORPHAN-TURN-END` or a `turn/start` that skips a number means the turn
  numbering itself is broken; reconstruct the turn sequence by hand before
  closing anything. (On a pre-release "legacy" log both findings are usually
  artifacts of the seed boundaries the harness normalizes — get the real verdict
  from `verify-session.mjs` first.)
- An unanswered `tool/call` inside the interrupted turn needs a synthetic error
  `tool/result` (the harness does this on resume); decide with the user whether
  to add one or to drop the turn.

Report honestly to the user; do not fabricate events.
