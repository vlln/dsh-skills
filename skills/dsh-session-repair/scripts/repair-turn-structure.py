#!/usr/bin/env python3
"""
repair-turn-structure.py — repair a DSH session log whose TURN structure is
broken: a `turn/start` arrives while the previous turn was never closed.

The harness's released-format migration refuses such a log outright:

    turn/start 39 does not close the prior turn;
    source v0 artifact remains unchanged (raw log: .../session.jsonl.zstd)

so the session cannot be opened in the GUI even though its seq stream is
perfectly contiguous — `check-session.py` reports the OPEN-TURN violation while
its seq check stays clean. This is a different defect from the duplicate/gap
seq classes handled by `repair-session.py`.

Exactly one mid-log open-turn shape is tolerated by the harness itself and is
therefore NOT repaired here: the *released resume restart*, whose event
immediately before the new `turn/start` is an `agent/inbox/spliced` insert with
`target: "next-turn"` and a non-empty `inserted`. For every other shape the log
is simply missing the closer the harness synthesizes on resume:

    turn/end {turn: <open>, reason: {kind: "interrupted"}}

(emitted after a `step/end` when a step is still open inside that turn, exactly
like the harness's crash-recovery closers). This script inserts those closers
immediately before the offending `turn/start`, renumbers every later event by
the number of closers inserted before it, and pushes every seq reference
(`sourceEventSeqs` / `messageSeqs` ranges) through the same mapping. Seq numbers
and reference ranges are edited textually, so every untouched byte of the log
stays untouched.

It fails closed — it never writes a log it cannot verify:

  * the seq stream must already be contiguous (run `repair-session.py` first);
  * the harness-recoverable restart shape is left alone;
  * a `turn/end` without a matching open turn, an unexpected turn number, or a
    turn/start that skips a number is reported for manual review;
  * an interrupted turn with an unanswered `tool/call` is refused: closing it
    would need a synthetic tool result, which this script does not fabricate.

Usage:
  repair-turn-structure.py <session.jsonl.zstd>
      [--out <path>]            write the repaired log here (default: <file>.fixed)
      [--install]               back up the original and replace it in place
      [--backup-dir <dir>]      backup location for --install (default: same dir)

Exit codes: 0 = repaired (and installed if requested), 1 = no corruption found,
2 = not auto-repairable, 3 = error.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

PACKED_TYPES = ('text-chunks', 'reasoning-chunks', 'tool-call-chunks')
REF_KEYS = ('"sourceEventSeqs":', '"messageSeqs":')
RECOVERY_SPLICE_TARGET = 'next-turn'
SEED_EVENT_ROW = re.compile(r'^\{"type":"session/end-seed"')
TOP_SEQ_MATCH = re.compile(r'^\{"type":"[^"]+","(?:seq|seq0)":(\d+)')
TOP_SEQ_BUMP = re.compile(r'^(\{"type":"[^"]+","(?:seq|seq0)":)(\d+)')


def decompress(path: str) -> str:
    proc = subprocess.run(['zstd', '-dc', '-q', path], capture_output=True)
    if proc.returncode != 0:
        raise IOError(f'zstd decompress failed: {proc.stderr.decode(errors="replace")[:200]}')
    return proc.stdout.decode('utf-8', errors='replace')


def encode_zstd(lines_text: str, tmpdir: str) -> bytes:
    """Header line as its own checksummed zstd frame, events as a body frame —
    the exact framing the harness writes (compressZstdFrame with checksum)."""
    raw_lines = lines_text.split('\n')
    if raw_lines[-1] == '':
        raw_lines.pop()
    header = raw_lines[0] + '\n'
    body = '\n'.join(raw_lines[1:]) + ('\n' if len(raw_lines) > 1 else '')
    hdr_path = os.path.join(tmpdir, 'hdr.txt')
    body_path = os.path.join(tmpdir, 'body.txt')
    with open(hdr_path, 'w') as f:
        f.write(header)
    with open(body_path, 'w') as f:
        f.write(body)
    f1 = subprocess.run(['zstd', '-q', '-c', '--check', hdr_path], capture_output=True, check=True)
    f2 = subprocess.run(['zstd', '-q', '-c', '--check', body_path], capture_output=True, check=True)
    return f1.stdout + f2.stdout


def decode_lines(plaintext: str):
    """Yield (line_index, seq_start, seq_end, event) per physical event line,
    skipping the header (index 0). Packed rows expand to a seq run."""
    for i, line in enumerate(plaintext.split('\n')):
        line = line.strip()
        if not line:
            continue
        if i == 0:
            continue
        v = json.loads(line)
        t = v.get('type')
        if t in PACKED_TYPES:
            members = v['data']['args'] if t == 'tool-call-chunks' else v['data']['texts']
            yield i, v['seq0'], v['seq0'] + len(members) - 1, v
        else:
            yield i, v['seq'], v['seq'], v


def top_seq(row: str) -> int:
    m = TOP_SEQ_MATCH.match(row)
    if m is None:
        raise ValueError(f'row has no top-level seq/seq0: {row[:120]!r}')
    return int(m.group(1))


def bump_top_seq(row: str, offset: int) -> str:
    if offset == 0:
        return row
    bumped, n = TOP_SEQ_BUMP.subn(
        lambda m: m.group(1) + str(int(m.group(2)) + offset), row, count=1)
    if n != 1:
        raise ValueError(f'row has no top-level seq/seq0: {row[:120]!r}')
    return bumped


def shift_references(row: str, mapper) -> str:
    """Rewrite every integer inside sourceEventSeqs/messageSeqs through mapper.

    The arrays are range lists (`[[start, end], ...]`), possibly nested under
    `data`; bracket scanning keeps the untouched bytes byte-identical.
    """
    for key in REF_KEYS:
        cursor = 0
        while True:
            start = row.find(key, cursor)
            if start < 0:
                break
            open_at = start + len(key)
            if row[open_at:open_at + 1] != '[':
                raise ValueError(f'{key} is not followed by an array')
            depth, end = 0, open_at
            while True:
                ch = row[end:end + 1]
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            content = re.sub(r'\d+', lambda m: str(mapper(int(m.group()))), row[open_at + 1:end])
            row = row[:open_at + 1] + content + row[end:]
            cursor = open_at + 2 + len(content)
    return row


def verify_contiguous(plaintext: str):
    """Mirror check-session.py: return (violation, count, max_seq)."""
    seen = set()
    expected = 0
    total = 0
    max_seq = -1
    for _line_idx, s0, s1, v in decode_lines(plaintext):
        if s0 != expected:
            if s0 in seen:
                kind = 'duplicate'
            elif s0 < expected:
                kind = 'out-of-order'
            else:
                kind = 'gap'
            return ({'line': _line_idx, 'type': v.get('type'), 'expected': expected, 'got': s0,
                     'kind': kind}, total, max_seq)
        seen.update(range(s0, s1 + 1))
        expected = s1 + 1
        total += s1 - s0 + 1
        max_seq = s1
    return (None, total, max_seq)


def scan_structure(rows, events):
    """Return (breaks, refusal). `breaks` lists the offending turn/start rows
    whose open turn must be closed; `refusal` is a manual-review message."""
    header = json.loads(rows[0])
    # Seed boundaries restart/segment turn numbering in pre-release logs, and a
    # break inside the inherited prefix cannot be closed without moving the cut.
    # Match the end-seed ROW TYPE (anchored), never a substring: session text
    # mentions event names freely.
    seed_rows = [i for i, row in enumerate(rows) if SEED_EVENT_ROW.match(row)]
    last_seed_row = max(seed_rows) if seed_rows else None
    if header.get('isSeeded') is True and last_seed_row is None and header.get('inheritedEventCount') not in (None, 0):
        return None, ('seeded header without a session/end-seed marker: the inherited prefix is not '
                      'in this file — manual review')

    open_turn = None
    open_step = None
    next_turn = 1
    prev = None
    open_calls = set()
    breaks = []

    for raw_index, v in events:
        t = v.get('type')
        d = v.get('data') or {}
        if t == 'turn/start':
            if 'trigger' in d:
                # Pre-release shape: the harness normalizes it (and its seed
                # boundaries may reset numbering) before validating, so this
                # script's turn model does not apply.
                return None, ('pre-release "legacy" format (turn/start carries a trigger): this script '
                              'does not model the harness normalization path — verify with verify-session.mjs')
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
                open_turn = None
                next_turn += 1
            if open_turn is not None:
                if turn != open_turn + 1:
                    return None, (f'turn/start {turn} at row {raw_index} skips from open turn {open_turn}')
                if last_seed_row is not None and raw_index <= last_seed_row:
                    return None, (f'open turn {open_turn} begins before the last session/end-seed marker '
                                  f'(row {last_seed_row}): it belongs to the inherited prefix, and closing it '
                                  'would move the inherited cut — manual review')
                if open_calls:
                    return None, (f'open turn {open_turn} has {len(open_calls)} unanswered tool call(s); '
                                  'closing it needs a synthetic tool/result, which this script does not fabricate')
                breaks.append({'row': raw_index, 'turn': open_turn, 'step': open_step,
                               'time': v.get('time'), 'seq': top_seq(rows[raw_index])})
                # Closing the abandoned turn consumes its number, so the new
                # turn/start keeps the expected numbering.
                next_turn = open_turn + 1
            if turn != next_turn:
                return None, (f'turn/start {turn} at row {raw_index} does not open the expected turn '
                              f'{next_turn} (seeded or renumbered log?)')
            open_turn = turn
            open_step = None
            open_calls = set()
        elif t == 'turn/end':
            turn = d.get('turn')
            if open_turn != turn:
                return None, f'turn/end {turn} at row {raw_index} has no matching open turn'
            if open_step is not None:
                return None, f'turn/end {turn} at row {raw_index} crosses an open step {open_step}'
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
            open_calls.discard(((d.get('message') or {}).get('source') or {}).get('callId'))
        prev = (t, d)
    return breaks, None


def closer_count(break_):
    return 2 if break_['step'] is not None else 1


def repair_file(path: str, out: str) -> str:
    plaintext = decompress(path)
    rows = plaintext.split('\n')
    if rows and rows[-1] == '':
        rows.pop()

    seq_viol, _total, _max = verify_contiguous(plaintext)
    if seq_viol is not None:
        return (f'NOT_REPAIRABLE: seq stream is not contiguous ({seq_viol["kind"]} seq '
                f'{seq_viol["got"]} at line {seq_viol["line"]}); run repair-session.py first')

    events = [(i, json.loads(rows[i])) for i in range(1, len(rows)) if rows[i].strip()]
    breaks, refusal = scan_structure(rows, events)
    if refusal is not None:
        return f'NOT_REPAIRABLE: {refusal}'
    if not breaks:
        return 'NO_CORRUPTION'

    # Old seqs of the offending turn/starts, which anchor the reference mapping.
    # An insertion point shifts the tail by its CLOSER COUNT (2 when a step is
    # still open), so references shift by the same amount, not by one per point.
    anchors = sorted((b['seq'], closer_count(b)) for b in breaks)

    def closers_before(raw_index: int) -> int:
        return sum(closer_count(b) for b in breaks if b['row'] < raw_index)

    def map_reference(seq: int) -> int:
        return seq + sum(count for old_seq, count in anchors if old_seq <= seq)

    out_rows = [rows[0]]
    for i in range(1, len(rows)):
        row = rows[i]
        if not row.strip():
            out_rows.append(row)
            continue
        for b in breaks:
            if b['row'] != i:
                continue
            seq = b['seq'] + closers_before(i)
            if b['step'] is not None:
                out_rows.append(json.dumps({'type': 'step/end', 'seq': seq, 'time': b['time'],
                                            'data': {'turn': b['turn'], 'step': b['step']}},
                                           separators=(',', ':')))
                seq += 1
            out_rows.append(json.dumps({'type': 'turn/end', 'seq': seq, 'time': b['time'],
                                        'data': {'turn': b['turn'], 'reason': {'kind': 'interrupted'}}},
                                       separators=(',', ':')))
        offset = closers_before(i) + sum(closer_count(b) for b in breaks if b['row'] == i)
        if offset:
            row = bump_top_seq(row, offset)
            if '"sourceEventSeqs"' in row or '"messageSeqs"' in row:
                row = shift_references(row, map_reference)
        out_rows.append(row)

    # Re-verify BOTH contracts before writing anything.
    repaired_text = '\n'.join(out_rows) + '\n'
    seq_viol2, total, max_seq = verify_contiguous(repaired_text)
    if seq_viol2 is not None:
        return (f'NOT_REPAIRABLE: repair did not restore seq contiguity '
                f'({seq_viol2["kind"]} at line {seq_viol2["line"]}) — manual review needed')
    repaired_events = [(i, json.loads(out_rows[i])) for i in range(1, len(out_rows)) if out_rows[i].strip()]
    breaks2, refusal2 = scan_structure(out_rows, repaired_events)
    if refusal2 is not None or breaks2:
        return (f'NOT_REPAIRABLE: repair did not restore turn structure '
                f'({refusal2 or f"{len(breaks2)} open turn(s) left"}) — manual review needed')

    with tempfile.TemporaryDirectory(prefix='dsh-repair-') as tmpdir:
        encoded = encode_zstd(repaired_text, tmpdir)
    with open(out, 'wb') as f:
        f.write(encoded)
    closed = ', '.join(str(b['turn']) for b in breaks)
    closers = sum(closer_count(b) for b in breaks)
    shifted = len(rows) - breaks[0]['row']
    return (f'turn structure: closed {len(breaks)} interrupted turn(s) [{closed}] with {closers} '
            f'synthetic closer(s) and shifted {shifted} following event row(s) '
            f'({total} events, seq 0..{max_seq}); wrote {out}')


def main() -> int:
    ap = argparse.ArgumentParser(description='Repair a DSH session log with broken turn structure')
    ap.add_argument('file', help='path to session.jsonl.zstd')
    ap.add_argument('--out', help='output path (default: <file>.fixed)')
    ap.add_argument('--install', action='store_true',
                    help='back up the original and replace it in place')
    ap.add_argument('--backup-dir', help='backup directory for --install')
    args = ap.parse_args()

    src = args.file
    if not os.path.isfile(src):
        print(f'error: no such file: {src}', file=sys.stderr)
        return 3

    out = args.out or (src + '.fixed')
    try:
        summary = repair_file(src, out)
    except (IOError, ValueError) as error:
        print(f'{src}: error: {error}', file=sys.stderr)
        return 3
    if summary == 'NO_CORRUPTION':
        print(f'{src}: no turn-structure corruption detected (nothing to repair)')
        return 1
    if summary.startswith('NOT_REPAIRABLE'):
        print(f'{src}: {summary}', file=sys.stderr)
        return 2
    print(f'{src}: {summary}')

    if args.install:
        backup_dir = args.backup_dir or os.path.dirname(os.path.abspath(src))
        os.makedirs(backup_dir, exist_ok=True)
        stamp = time.strftime('%Y%m%dT%H%M%S')
        backup = os.path.join(backup_dir, os.path.basename(src) + f'.bak-{stamp}')
        os.replace(src, backup)
        os.replace(out, src)
        os.chmod(src, 0o600)
        print(f'installed {src} (original backed up at {backup})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
