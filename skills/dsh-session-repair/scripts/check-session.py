#!/usr/bin/env python3
"""
check-session.py — validate DSH session JSONL logs (zstd) for the two
independent defects that each make a whole session unloadable in the GUI.

1. Seq contiguity — the decoded event stream must be strictly contiguous
   seq 0,1,2,...,N: no duplicates, no gaps, no out-of-order events. The
   persistence scanner (`SessionLogScanner` in
   `@deepseek-ai/dsh-session-persistence-jsonl`) rejects the WHOLE log when one
   line violates this ("corrupt Zstandard session log: complete frame contains
   a torn JSONL record"). Cause: concurrent multi-client writes.

2. Turn structure — at most ONE turn may be open at a time. The harness's
   released-format migration refuses a `turn/start` that arrives while the
   previous turn was never closed ("turn/start N does not close the prior
   turn"); the session then fails to load even though every seq is perfectly
   contiguous, and the seq check above reports OK. The harness recovers from
   exactly ONE shape here: the *released resume restart*, whose event
   immediately before the new `turn/start` is an `agent/inbox/spliced` insert
   with `target: "next-turn"` and a non-empty `inserted`. Every other shape is
   a hard violation.

Packed chunk rows (text-chunks / reasoning-chunks / tool-call-chunks) carry no
top-level `seq`; they carry `seq0` and expand to seq0..seq0+len-1, so checks
must expand them. The header line (type "session") is consumed separately by
the scanner and is skipped here.

Usage:
  check-session.py <session.jsonl.zstd> [<file2> ...]
  check-session.py --all [--root ~/.dsh/sessions]

Exit codes: 0 = all clean, 1 = at least one violation found, 2 = I/O error.
"""
import argparse
import json
import os
import re
import subprocess
import sys

PACKED_TYPES = ('text-chunks', 'reasoning-chunks', 'tool-call-chunks')
# The only mid-log open-turn shape the harness itself recovers from.
RECOVERY_SPLICE_TARGET = 'next-turn'
# A seeded/forked log ends its inherited prefix with this event. Match the ROW
# TYPE (anchored), never a substring: session text routinely mentions event
# names, and a loose search flags thousands of healthy logs.
SEED_EVENT_ROW = re.compile(r'^\{"type":"session/end-seed"')
# Event rows that can change the turn/step state machine we mirror below.
# Anything else cannot change the state, but it DOES break the "immediately
# preceding event" test, so skipped rows clear `prev`.
STRUCTURE_MARKERS = (
    '"type":"turn/start"', '"type":"turn/end"',
    '"type":"step/start"', '"type":"step/end"',
    '"type":"tool/call"', '"type":"tool/result"',
    '"type":"agent/inbox/spliced"',
)


def decode_lines(plaintext: str):
    """Yield (line_index, seq_start, seq_end, event) per physical event line.

    Skips the header line (index 0). seq_start/seq_end describe the seq range
    a line contributes (a packed row contributes a whole run).
    """
    for i, line in enumerate(plaintext.split('\n')):
        line = line.strip()
        if not line:
            continue
        if i == 0:
            continue  # header record, consumed separately by the scanner
        v = json.loads(line)
        t = v.get('type')
        if t in PACKED_TYPES:
            members = v['data']['args'] if t == 'tool-call-chunks' else v['data']['texts']
            yield i, v['seq0'], v['seq0'] + len(members) - 1, v
        else:
            yield i, v['seq'], v['seq'], v


def decompress(path: str) -> str:
    proc = subprocess.run(['zstd', '-dc', '-q', path], capture_output=True)
    if proc.returncode != 0:
        raise IOError(f'zstd decompress failed: {proc.stderr.decode(errors="replace")[:200]}')
    return proc.stdout.decode('utf-8', errors='replace')


def check_plaintext(plaintext: str):
    """Return (first_violation, event_count, max_seq) where first_violation is
    a dict or None. first_violation keys: line, type, expected, got, kind.
    """
    seen = set()
    expected = 0  # next expected seq
    total = 0
    max_seq = -1
    for line_idx, s0, s1, v in decode_lines(plaintext):
        if s0 != expected:
            if s0 in seen:
                kind = 'duplicate'
            elif s0 < expected:
                kind = 'out-of-order'
            else:
                kind = 'gap'
            return ({'line': line_idx, 'type': v.get('type'), 'expected': expected,
                     'got': s0, 'kind': kind}, total, max_seq)
        # contiguous run: s0..s1 all fresh
        seen.update(range(s0, s1 + 1))
        expected = s1 + 1
        total += s1 - s0 + 1
        max_seq = s1
    return (None, total, max_seq)


def header_of(plaintext: str) -> dict:
    return json.loads(plaintext.split('\n', 1)[0])


def check_structure(plaintext: str):
    """Mirror the harness's turn-level relationship rules.

    Returns (violation, notes, skipped) where violation is the first hard
    violation (dict or None), notes are recoverable/synthetic shapes worth
    reporting, and skipped is a reason string when the check cannot be applied
    (pre-release "legacy" logs are normalized by the harness before they are
    validated, so this approximation does not model them).
    """
    header = header_of(plaintext)
    seeded = (header.get('isSeeded') is True
              or header.get('inheritedEventCount') not in (None, 0)
              or any(SEED_EVENT_ROW.match(line) for line in plaintext.split('\n')))

    notes = []
    open_turn = None
    open_step = None
    next_turn = 1
    prev = None  # the immediately preceding event row (type, data)
    open_calls = set()  # callIds started and not yet answered inside the open turn

    for line_idx, line in enumerate(plaintext.split('\n')):
        if not line.strip() or line_idx == 0:
            continue
        if not any(marker in line for marker in STRUCTURE_MARKERS):
            prev = None  # an unexamined event row breaks the adjacency test
            continue
        v = json.loads(line)
        t = v.get('type')
        d = v.get('data') or {}

        if t == 'turn/start':
            if 'trigger' in d:
                # Pre-release shape: normalizeLegacyTurnStart drops `trigger`
                # and the harness validates the normalized stream, where seed
                # boundaries may reset turn numbering. Do not guess.
                return (None, notes, 'pre-release "legacy" format (turn/start carries a trigger): the '
                                     'harness normalizes turn structure before validating, so this check '
                                     'does not apply — use verify-session.mjs')
            turn = d.get('turn')
            recovered = (
                open_turn is not None
                and open_step is None
                and turn == open_turn + 1
                and next_turn == open_turn
                and prev is not None
                and prev[0] == 'agent/inbox/spliced'
                and (prev[1] or {}).get('target') == RECOVERY_SPLICE_TARGET
                and isinstance((prev[1] or {}).get('inserted'), list)
                and len((prev[1] or {}).get('inserted')) > 0
            )
            if recovered:
                notes.append({'kind': 'recovered', 'line': line_idx, 'turn': open_turn, 'next': turn})
                open_turn = None
                next_turn += 1
            if open_turn is not None:
                return ({'kind': 'open-turn', 'line': line_idx, 'type': t,
                         'turn': open_turn, 'open_step': open_step, 'next': turn,
                         'preceding': prev[0] if prev else None,
                         'target': (prev[1] or {}).get('target') if prev and prev[0] == 'agent/inbox/spliced' else None}, notes, None)
            if turn != next_turn:
                return ({'kind': 'turn-number', 'line': line_idx, 'type': t,
                         'expected': next_turn, 'got': turn}, notes, None)
            open_turn = turn
            open_step = None
            open_calls = set()
        elif t == 'turn/end':
            turn = d.get('turn')
            if open_turn != turn:
                return ({'kind': 'orphan-turn-end', 'line': line_idx, 'type': t,
                         'got': turn, 'open_turn': open_turn}, notes, None)
            if open_step is not None:
                return ({'kind': 'turn-end-open-step', 'line': line_idx, 'type': t,
                         'turn': turn, 'step': open_step}, notes, None)
            open_turn = None
            open_step = None
            open_calls = set()
            next_turn = turn + 1
        elif t == 'step/start':
            open_step = d.get('step')
        elif t == 'step/end':
            open_step = None
        elif t == 'tool/call':
            open_calls.add(d.get('callId'))
        elif t == 'tool/result':
            call = ((d.get('message') or {}).get('source') or {}).get('callId')
            open_calls.discard(call)
        prev = (t, d)

    if open_turn is not None:
        # A trailing open turn is the normal crash shape: the harness appends
        # synthetic closers when the session is resumed, so it is not a defect.
        notes.append({'kind': 'trailing', 'line': None, 'turn': open_turn,
                      'step': open_step, 'unanswered_calls': len(open_calls)})
    if seeded:
        # Released seeded logs still carry the full stream, so the turn check
        # holds (verified across a whole store); the note only warns that the
        # numbering may start inside an inherited prefix.
        notes.append({'kind': 'seeded', 'line': None})
    return (None, notes, None)


def describe_structural(violation: dict) -> str:
    kind = violation['kind']
    if kind == 'open-turn':
        why = f'preceding {violation["preceding"]}'
        if violation['target'] is not None:
            why += f' targets "{violation["target"]}"'
        else:
            why = 'no preceding inbox insert'
        return (f'OPEN-TURN turn {violation["turn"]} is still open at turn/start '
                f'{violation["next"]} line {violation["line"]} — the harness cannot recover it '
                f'({why}); open step: {violation["open_step"]}')
    if kind == 'turn-number':
        return (f'TURN-NUMBER turn/start {violation["got"]} at line {violation["line"]} '
                f'does not open the expected turn {violation["expected"]}')
    if kind == 'orphan-turn-end':
        return (f'ORPHAN-TURN-END turn/end {violation["got"]} at line {violation["line"]} '
                f'has no matching open turn (open: {violation["open_turn"]})')
    return (f'TURN-END-OPEN-STEP turn/end {violation["turn"]} at line {violation["line"]} '
            f'crosses an open step {violation["step"]}')


def check_file(path: str, verbose: bool = True) -> bool:
    try:
        plaintext = decompress(path)
    except IOError as e:
        print(f'{path}: DECOMPRESS ERROR: {e}')
        return False
    seq_viol, total, max_seq = check_plaintext(plaintext)
    struct_viol, notes, skipped = check_structure(plaintext)

    ok = seq_viol is None and struct_viol is None
    if ok:
        print(f'{path}: OK ({total} events, seq 0..{max_seq})')
    else:
        if seq_viol is not None:
            print(f'{path}: {seq_viol["kind"].upper()} seq {seq_viol["got"]} at {seq_viol["type"]} '
                  f'line {seq_viol["line"]} (expected {seq_viol["expected"]})')
        if struct_viol is not None:
            print(f'{path}: {describe_structural(struct_viol)}')
    if verbose:
        if skipped is not None:
            print(f'{path}:   note: {skipped}')
        for note in notes:
            if note['kind'] == 'recovered':
                print(f'{path}:   note: open turn {note["turn"]} is closed by the harness itself as '
                      f'"interrupted" (turn/start {note["next"]} line {note["line"]} after a '
                      f'"{RECOVERY_SPLICE_TARGET}" inbox insert)')
            elif note['kind'] == 'trailing':
                extra = (f', {note["unanswered_calls"]} unanswered tool call(s)'
                         if note['unanswered_calls'] else '')
                print(f'{path}:   note: trailing open turn {note["turn"]} (open step {note["step"]}{extra}) '
                      f'— normal crash shape, the harness synthesizes closers on resume')
            elif note['kind'] == 'seeded':
                print(f'{path}:   note: seeded/inherited log (a session/end-seed marker is present); the '
                      f'turn check above still applies, but a violation may belong to the inherited prefix')
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description='Check DSH session logs for seq and turn-structure corruption')
    ap.add_argument('files', nargs='*', help='session.jsonl.zstd paths')
    ap.add_argument('--all', action='store_true', help='scan the whole sessions root')
    ap.add_argument('--quiet-notes', action='store_true',
                    help='with --all, print only files that fail')
    ap.add_argument('--root', default=os.path.expanduser('~/.dsh/sessions'),
                    help='sessions root for --all (default ~/.dsh/sessions)')
    args = ap.parse_args()

    files = list(args.files)
    if args.all:
        for dirpath, _dirs, names in os.walk(args.root):
            if 'session.jsonl.zstd' in names:
                files.append(os.path.join(dirpath, 'session.jsonl.zstd'))
    if not files:
        ap.error('no files given (pass paths or --all)')

    bad = 0
    for f in sorted(files):
        if not check_file(f, verbose=not args.quiet_notes):
            bad += 1
    if bad:
        print(f'{bad}/{len(files)} log(s) corrupted')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
