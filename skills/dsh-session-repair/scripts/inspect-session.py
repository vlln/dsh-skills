#!/usr/bin/env python3
"""inspect-session.py — read-only view of one stored DSH session log.

Repairing a session starts with knowing what it actually contains: which working
directory it records (and whether that directory still exists), how the last turn
ended, and what the user/assistant actually said. This script answers those three
questions without mutating anything and without the GUI.

    inspect-session.py find    <session-id | path/to/log>   [--store DIR]
    inspect-session.py header  <path/to/log> [more ...]
    inspect-session.py tail    <path/to/log> [-n 20]
    inspect-session.py messages <path/to/log> [--limit 6] [--all]
    inspect-session.py stats   <path/to/log>

`--store` defaults to `~/.dsh/sessions` (project dirs are the cwd with `/` → `-`).

Why this exists next to check-session.py / verify-session.mjs:

  * `check-session.py`   — contract checker: is this log *valid*?
  * `verify-session.mjs` — authority: can the installed harness *load* it?
  * `inspect-session.py` — evidence: what is *in* it, in human terms.

Reading is always safe on a live session; writing is not (see SKILL.md).
"""
import argparse
import json
import os
import subprocess
import sys

STORE = os.path.expanduser('~/.dsh/sessions')


def log_paths(store, session_id):
    """Every stored generation for one id (project dirs vary; scan them all)."""
    root = os.path.expanduser(store)
    hits = []
    for project in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        session_dir = os.path.join(root, project, session_id)
        if not os.path.isdir(session_dir):
            continue
        for name in sorted(os.listdir(session_dir)):
            if name.startswith('session') and name.endswith('.jsonl.zstd'):
                hits.append(os.path.join(session_dir, name))
    return hits


def resolve(target, store):
    """Accept a path or a bare session id; return the log path to read."""
    if os.path.isfile(target):
        return target
    if os.path.isdir(target):
        candidates = [n for n in sorted(os.listdir(target))
                      if n.startswith('session') and n.endswith('.jsonl.zstd')]
        if candidates:
            return os.path.join(target, candidates[0])
        raise SystemExit(f'{target}: no session log inside this directory')
    hits = log_paths(store, target)
    if not hits:
        raise SystemExit(f'no stored log for session {target!r} under {store}')
    # prefer the newest format generation (session.v4.* before session.v3.* ...)
    hits.sort(key=lambda p: ('session.v4' not in p, 'session.v3' not in p, p))
    if len(hits) > 1:
        print(f'note: {len(hits)} generations found, reading {os.path.basename(hits[0])}', file=sys.stderr)
    return hits[0]


def read_lines(path):
    proc = subprocess.run(['zstd', '-dc', '-q', path], capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f'zstd failed on {path}: {proc.stderr.decode("utf-8", "replace")[:200]}')
    return proc.stdout.decode('utf-8', 'replace').split('\n')


def load(path):
    """Return (header, events). The header is line 1 of the first frame."""
    lines = [line for line in read_lines(path) if line.strip()]
    if not lines:
        raise SystemExit(f'{path}: empty log')
    header = json.loads(lines[0])
    events = []
    for line in lines[1:]:
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return header, events


def message_text(event):
    data = event.get('data') or {}
    msg = data.get('message') or data
    content = msg.get('content')
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return ''.join(block.get('text', '') for block in content if isinstance(block, dict) and block.get('type') == 'text')


def summarize(event):
    """One short line for the tail view."""
    kind = event.get('type')
    data = event.get('data') or {}
    if kind == 'turn/start':
        return f'turn={data.get("turn")}'
    if kind == 'turn/end':
        reason = (data.get('reason') or {}).get('kind')
        return f'turn={data.get("turn")} reason={reason}'
    if kind == 'step/start':
        return f'turn={data.get("turn")} step={data.get("step")}'
    if kind == 'step/end':
        return f'turn={data.get("turn")} step={data.get("step")}'
    if kind == 'tool/call':
        return f'{data.get("name")} id={data.get("id") or data.get("callId") or ""}'
    if kind == 'tool/result':
        return f'id={data.get("id") or data.get("callId") or ""}'
    if kind == 'session/title':
        return repr(data.get('title'))
    if kind == 'working-directory/change':
        return str(data.get('cwd'))
    if kind in ('user/message', 'assistant/message'):
        source = ((data.get('message') or data).get('source') or {}).get('kind')
        text = message_text(event).strip().replace('\n', ' ⏎ ')
        return f'{source or "-"} :: {text[:100]}'
    return ''


def cmd_find(args):
    hits = log_paths(args.store, args.target)
    if not hits:
        print(f'not found: {args.target}')
        return 1
    for path in hits:
        print(path)
    return 0


def cmd_header(args):
    for target in args.targets:
        path = resolve(target, args.store)
        header, events = load(path)
        cwd = header.get('cwd')
        size = os.path.getsize(path)
        fields = {
            'file': path,
            'id': header.get('id'),
            'format': header.get('version'),
            'createdAt': header.get('createdAt'),
            'cwd': cwd,
            'cwd exists': ('yes' if cwd and os.path.isdir(cwd) else 'NO'),
            'origin': header.get('origin') or 'main',
            'parentSession': header.get('parentSession'),
            'agentPreset': header.get('agentPreset'),
            'isSeeded': header.get('isSeeded'),
            'events': len(events),
            'bytes': size,
        }
        for key, value in fields.items():
            print(f'{key:12} {value}')
        if cwd and not os.path.isdir(cwd):
            print('warning      recorded cwd is missing: a turn cannot start until it is restored '
                  '(see references/workdir-migration.md)')
        print()
    return 0


def cmd_tail(args):
    path = resolve(args.target, args.store)
    header, events = load(path)
    print(f'# {header.get("id")}  cwd={header.get("cwd")}  events={len(events)}')
    open_turn = None
    for event in events[-args.n:]:
        line = summarize(event)
        print(f'{event.get("seq"):>8}  {event.get("type"):<22} {line}')
    for event in events:
        if event.get('type') == 'turn/start':
            open_turn = (event.get('data') or {}).get('turn')
        elif event.get('type') == 'turn/end':
            open_turn = None
    if open_turn is not None:
        print(f'\nnote: turn {open_turn} is open (no turn/end) — a trailing open turn is closed '
              'as interrupted on resume; a mid-log one is the turn-structure family')
    return 0


def cmd_messages(args):
    path = resolve(args.target, args.store)
    header, events = load(path)
    shown = 0
    for event in events:
        if event.get('type') not in ('user/message', 'assistant/message'):
            continue
        data = event.get('data') or {}
        source = ((data.get('message') or data).get('source') or {}).get('kind')
        if event['type'] == 'user/message' and not args.all and source != 'user':
            continue
        text = message_text(event).strip()
        if not text:
            continue
        shown += 1
        print(f'--- [{event.get("seq")}] {event["type"].replace("/message", "")}'
              f'{"" if source in (None, "user") else f" ({source})"}\n{text[:1500]}\n')
        if args.limit and shown >= args.limit:
            break
    if shown == 0:
        print('(no matching messages)')
    return 0


def cmd_stats(args):
    path = resolve(args.target, args.store)
    header, events = load(path)
    counts = {}
    for event in events:
        counts[event.get('type')] = counts.get(event.get('type'), 0) + 1
    packed = {'text-chunks', 'reasoning-chunks', 'tool-call-chunks'}
    ranges = []
    for event in events:
        kind = event.get('type')
        if kind in packed and isinstance(event.get('seq0'), int):
            members = (event.get('data') or {}).get('texts') or (event.get('data') or {}).get('args') or []
            ranges.append((event['seq0'], event['seq0'] + max(len(members), 1) - 1))
        elif isinstance(event.get('seq'), int):
            ranges.append((event['seq'], event['seq']))
    print(f'id       {header.get("id")}')
    print(f'events   {len(events)}')
    if ranges:
        ranges.sort()
        contiguous = ranges[0][0] == 0 and all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))
        print(f'logical  seq {ranges[0][0]}..{ranges[-1][1]}  (contiguous: '
              f'{"yes" if contiguous else "NO — run check-session.py"})')
    print('types:')
    for kind, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f'  {count:>6}  {kind}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', default=STORE, help='session store root (default: ~/.dsh/sessions)')
    sub = ap.add_subparsers(dest='command', required=True)

    p = sub.add_parser('find', help='locate the log(s) for a session id')
    p.add_argument('target')
    p.set_defaults(func=cmd_find)

    p = sub.add_parser('header', help='header fields, with a cwd-exists check')
    p.add_argument('targets', nargs='+')
    p.set_defaults(func=cmd_header)

    p = sub.add_parser('tail', help='last N events, one line each')
    p.add_argument('target')
    p.add_argument('-n', type=int, default=15)
    p.set_defaults(func=cmd_tail)

    p = sub.add_parser('messages', help='conversation text (injected context filtered out)')
    p.add_argument('target')
    p.add_argument('--limit', type=int, default=0, help='0 = all')
    p.add_argument('--all', action='store_true', help='include injected context messages')
    p.set_defaults(func=cmd_messages)

    p = sub.add_parser('stats', help='event-type histogram and seq range')
    p.add_argument('target')
    p.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
