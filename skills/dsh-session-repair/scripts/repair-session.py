#!/usr/bin/env python3
"""
repair-session.py — repair a DSH session JSONL log corrupted by concurrent
multi-client writes (two clients opening/continuing the same session).

The decoded event stream must be strictly contiguous seq 0..N. A second
writer that resumed the session from a STALE watermark appends events whose
seqs repeat already-committed values, which makes the harness's scanner reject
the WHOLE log ("corrupt Zstandard session log: complete frame contains a torn
JSONL record"). Two corruption classes are auto-repairable:

  A) stale tail   — the real content ends; the stale writer's appended suffix
                    duplicates already-committed seqs. Fix: truncate the tail
                    at the first duplicated line.
  B) stale counter — a resumed writer reused one old seq (typically duplicating
                    the preceding session/end-seed), then continued with NEW
                    ascending seqs. Fix: shift every event from the duplicated
                    line onward by the offset that restores contiguity
                    (seq, packed-row seq0, and seq-reference fields
                    sourceEventSeqs / messageSeqs all shift together).

Anything else (gaps, out-of-order with mixed patterns) is NOT auto-repairable:
the script fails closed and asks for manual review — it never writes a file it
cannot verify.

Usage:
  repair-session.py <session.jsonl.zstd>
      [--out <path>]            write the repaired log here (default: <file>.fixed)
      [--install]               back up the original and replace it in place
      [--backup-dir <dir>]      backup location for --install (default: same dir)
      [--force]                 allow --install even if a backup cannot be made

Exit codes: 0 = repaired (and installed if requested), 1 = no corruption
found, 2 = corruption not auto-repairable, 3 = error.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

PACKED_TYPES = ('text-chunks', 'reasoning-chunks', 'tool-call-chunks')
REF_FIELDS = ('sourceEventSeqs', 'messageSeqs')


def decode_lines(plaintext: str):
    """Yield (line_index, seq_start, seq_end, event) per physical event line,
    skipping the header (index 0)."""
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


def scan_events(plaintext: str):
    """Full-file scan: build the complete event list and detect the first
    violation (if any). Unlike a pure check, this must see everything — the
    Type A/B classifier needs the events AFTER the first violation.

    Returns (first_violation_or_None, lines, event_lines) where event_lines is
    the full list of (line_index, event, is_packed, member_count).
    """
    lines = plaintext.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    seen = set()
    expected = 0
    event_lines = []
    first_viol = None
    for line_idx, s0, s1, v in decode_lines(plaintext):
        is_packed = v.get('type') in PACKED_TYPES
        event_lines.append((line_idx, v, is_packed, (s1 - s0 + 1) if is_packed else 1))
        if first_viol is None and s0 != expected:
            if s0 in seen:
                kind = 'duplicate'
            elif s0 < expected:
                kind = 'out-of-order'
            else:
                kind = 'gap'
            first_viol = {'line': line_idx, 'type': v.get('type'), 'expected': expected,
                          'got': s0, 'kind': kind}
            continue  # stop trusting seqs past the break; keep collecting lines
        if first_viol is None:
            seen.update(range(s0, s1 + 1))
            expected = s1 + 1
    return (first_viol, lines, event_lines)


def all_subsequent_are_duplicates(event_lines, first_pos):
    """Type A test: every event after first_pos repeats an already-seen seq."""
    seen = set()
    for line_idx, v, is_packed, count in event_lines[:first_pos]:
        if is_packed:
            seen.update(range(v['seq0'], v['seq0'] + count))
        else:
            seen.add(v['seq'])
    for line_idx, v, is_packed, count in event_lines[first_pos:]:
        if is_packed:
            for k in range(count):
                if v['seq0'] + k not in seen:
                    return False
        else:
            if v['seq'] not in seen:
                return False
    return True


def shift_events(lines, first_pos, event_lines, offset, threshold):
    """Apply +offset to seqs/seq0 and to seq-reference fields of every event
    line from first_pos onward. References pointing below `threshold` (outside
    the shifted region) are left untouched. Returns the modified lines list."""
    for line_idx, v, is_packed, count in event_lines[first_pos:]:
        if is_packed:
            v['seq0'] += offset
        else:
            v['seq'] += offset
        for field in REF_FIELDS:
            if field in v:
                v[field] = [s + offset if s >= threshold else s for s in v[field]]
        lines[line_idx] = json.dumps(v)
    return lines


def verify_contiguous(plaintext: str):
    """Same validation as check-session.py: return (violation, count, max_seq)."""
    seen = set()
    expected = 0
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
        seen.update(range(s0, s1 + 1))
        expected = s1 + 1
        total += s1 - s0 + 1
        max_seq = s1
    return (None, total, max_seq)


def repair_file(path: str, out: str) -> str:
    """Returns a short human summary of what was done."""
    plaintext = decompress(path)
    lines = plaintext.split('\n')
    if lines and lines[-1] == '':
        lines.pop()

    viol, lines, event_lines = scan_events(plaintext)
    if viol is None:
        return 'NO_CORRUPTION'

    if viol['kind'] == 'duplicate' or viol['kind'] == 'out-of-order':
        first_pos = next(i for i, (li, _v, _p, _c) in enumerate(event_lines)
                         if li == viol['line'])
        if all_subsequent_are_duplicates(event_lines, first_pos):
            # Type A: truncate the stale tail at the first duplicated line.
            keep = event_lines[first_pos][0]  # physical line index of the first bad event
            new_lines = lines[:keep]
            action = (f'type A (stale tail): truncated {len(lines) - keep} stale line(s) '
                      f'after line {keep - 1}')
        elif viol['kind'] == 'duplicate':
            # Type B: a resumed writer reused an old seq then continued.
            offset = viol['expected'] - viol['got']
            if offset <= 0:
                return 'NOT_REPAIRABLE: cannot derive a positive shift offset'
            threshold = viol['got']
            shift_events(lines, first_pos, event_lines, offset, threshold)
            new_lines = lines
            action = (f'type B (stale counter): shifted {len(event_lines) - first_pos} '
                      f'event line(s) from seq {threshold} by +{offset}')
        else:
            return (f'NOT_REPAIRABLE: first violation is out-of-order (line '
                    f'{viol["line"]}) with mixed tail — manual review needed')
    else:
        return (f'NOT_REPAIRABLE: seq gap at line {viol["line"]} (expected '
                f'{viol["expected"]}, got {viol["got"]}) — missing events, '
                'manual review needed')

    # Re-verify the repaired stream before writing anything.
    repaired_text = '\n'.join(new_lines) + '\n'
    viol2, total, max_seq = verify_contiguous(repaired_text)
    if viol2 is not None:
        return (f'NOT_REPAIRABLE: repair did not restore contiguity '
                f'({viol2["kind"]} at line {viol2["line"]}) — manual review needed')

    with tempfile.TemporaryDirectory(prefix='dsh-repair-') as tmpdir:
        encoded = encode_zstd(repaired_text, tmpdir)
    with open(out, 'wb') as f:
        f.write(encoded)
    return f'{action}; wrote {out} ({total} events, seq 0..{max_seq})'


def main() -> int:
    ap = argparse.ArgumentParser(description='Repair a corrupted DSH session log')
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
    summary = repair_file(src, out)
    if summary == 'NO_CORRUPTION':
        print(f'{src}: no corruption detected (nothing to repair)')
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
