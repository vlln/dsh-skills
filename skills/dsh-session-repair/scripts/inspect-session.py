#!/usr/bin/env python3
"""inspect-session.py — read-only reader for stored DSH session logs.

Finding a session is the hard part: ids are invisible in the GUI and unknown to an
agent, while titles, working directories and recency are what people actually have.
So every read command accepts a *selector* instead of an id:

    <session-id | path/to/log | session dir>   positional
    --latest                                   most recently written session
    --title <substr>                           match the cached title
    --cwd <substr>                             match the recorded working directory

Ambiguous selectors list the candidates instead of guessing.

    inspect-session.py list     [--title S] [--cwd S] [--since DAYS] [--limit N] [--full-id]
    inspect-session.py search   <pattern> [--cwd S] [--title S] [--since DAYS] [--roles user,assistant]
    inspect-session.py header   [selector]
    inspect-session.py tail     [selector] [-n 20]
    inspect-session.py messages [selector] [--roles user] [--last] [--limit N] [--grep S] [--all]
    inspect-session.py stats    [selector]

`--store` defaults to `~/.dsh/sessions`; `--cache` to
`<store>/../storages/session_projcache/sessions` (the projection cache is the cheap
index: one small JSON per session holding title, cwd and createdAt — no log
decompression needed, which is why `list` and `--title/--cwd` stay fast).

What it does NOT do: it never writes. Writing to a session log needs the
`session.lock` discipline described in SKILL.md; use the repair scripts for that.

Companion commands:
  * `check-session.py`   — contract checker: is this log *valid*?
  * `verify-session.mjs` — authority: can the installed harness *load* it?
  * `inspect-session.py` — evidence: what is *in* it, in human terms.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

STORE = os.path.expanduser('~/.dsh/sessions')


# ---------------------------------------------------------------- stores ----

def default_cache(store):
    return os.path.join(os.path.dirname(os.path.abspath(os.path.expanduser(store))),
                        'storages', 'session_projcache', 'sessions')


def project_dirs(store):
    root = os.path.expanduser(store)
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, name) for name in sorted(os.listdir(root))
            if not name.startswith('.') and os.path.isdir(os.path.join(root, name))]


def session_dirs(store):
    for project in project_dirs(store):
        for name in sorted(os.listdir(project)):
            path = os.path.join(project, name)
            if os.path.isdir(path):
                yield path


def log_in(session_dir):
    names = [n for n in sorted(os.listdir(session_dir))
             if n.startswith('session') and n.endswith('.jsonl.zstd')]
    if not names:
        return None
    # newest generation first: session.v4.* > session.v3.* > session.jsonl.*
    names.sort(key=lambda n: ('session.v4' not in n, 'session.v3' not in n, n))
    return os.path.join(session_dir, names[0])


def all_logs(store):
    for session_dir in session_dirs(store):
        path = log_in(session_dir)
        if path:
            yield session_dir, path


# ----------------------------------------------------------------- cache ----

def cache_index(cache_dir):
    """id -> {title, cwd, createdAt} — the cheap index, no log reads."""
    index = {}
    if not cache_dir or not os.path.isdir(cache_dir):
        return index
    for name in os.listdir(cache_dir):
        if not name.endswith('.json'):
            continue
        path = os.path.join(cache_dir, name)
        try:
            doc = json.load(open(path))
        except (ValueError, OSError):
            continue
        record = doc.get('record') or {}
        identity = record.get('identity') or {}
        title = ((record.get('rows') or {}).get('title') or {}).get('val')
        index[name[:-5]] = {
            'title': title,
            'cwd': identity.get('cwd'),
            'createdAt': identity.get('createdAt'),
        }
    return index


def entries(store, cache_dir):
    """One record per stored session: id, log path, mtime, title, cwd."""
    index = cache_index(cache_dir)
    out = []
    for session_dir, log in all_logs(store):
        session_id = os.path.basename(session_dir)
        try:
            mtime = os.path.getmtime(log)
        except OSError:
            continue
        meta = index.get(session_id, {})
        out.append({
            'id': session_id,
            'path': log,
            'mtime': mtime,
            'title': meta.get('title'),
            'cwd': meta.get('cwd'),
            'createdAt': meta.get('createdAt'),
        })
    return out


def short_id(session_id):
    """The distinguishing part: ids look like session-<uuid>."""
    core = session_id[len('session-'):] if session_id.startswith('session-') else session_id
    return core[:8]


def age(seconds):
    if seconds < 90:
        return f'{int(seconds)}s'
    if seconds < 90 * 60:
        return f'{int(seconds / 60)}m'
    if seconds < 48 * 3600:
        return f'{int(seconds / 3600)}h'
    return f'{int(seconds / 86400)}d'


# --------------------------------------------------------------- reading ----

def read_lines(path):
    proc = subprocess.run(['zstd', '-dc', '-q', path], capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f'zstd failed on {path}: {proc.stderr.decode("utf-8", "replace")[:200]}')
    return proc.stdout.decode('utf-8', 'replace').split('\n')


def load(path):
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
    return ''.join(block.get('text', '') for block in content
                   if isinstance(block, dict) and block.get('type') == 'text')


def message_source(event):
    data = event.get('data') or {}
    return ((data.get('message') or data).get('source') or {}).get('kind')


def is_conversation(event):
    return event.get('type') in ('user/message', 'assistant/message')


def one_line(text, limit=120):
    return re.sub(r'\s+', ' ', text)[:limit]


# ------------------------------------------------------------- selecting ----

def resolve_target(target, store):
    if os.path.isfile(target):
        return target
    if os.path.isdir(target):
        path = log_in(target)
        if path:
            return path
        raise SystemExit(f'{target}: no session log inside this directory')
    root = os.path.expanduser(store)
    for project in project_dirs(root):
        session_dir = os.path.join(project, target)
        if os.path.isdir(session_dir):
            path = log_in(session_dir)
            if path:
                return path
    raise SystemExit(f'no stored log for {target!r} under {root}')


def pick(args):
    """Resolve a selector to exactly one log path; never guess when ambiguous."""
    if getattr(args, 'target', None):
        return resolve_target(args.target, args.store)

    rows = entries(args.store, args.cache or default_cache(args.store))
    filters = []
    if getattr(args, 'title', None):
        needle = args.title.lower()
        rows = [r for r in rows if needle in (r['title'] or '').lower()]
        filters.append(f'--title {args.title!r}')
    if getattr(args, 'cwd', None):
        needle = args.cwd.lower()
        rows = [r for r in rows if needle in (r['cwd'] or '').lower()]
        filters.append(f'--cwd {args.cwd!r}')
    if getattr(args, 'latest', False):
        filters.append('--latest')
    if not filters:
        raise SystemExit('no selector: pass <id|path/dir>, --latest, --title or --cwd')

    label = ' '.join(filters)
    if not rows:
        raise SystemExit(f'no session matches {label}')
    rows.sort(key=lambda r: r['mtime'], reverse=True)
    if len(rows) == 1 or getattr(args, 'latest', False):
        if len(rows) > 1 and len(filters) > 1:
            print(f'note: {len(rows)} sessions match {label}; reading the newest '
                  f'({short_id(rows[0]["id"])}, {age(time.time() - rows[0]["mtime"])} old)', 
                  file=sys.stderr)
        return rows[0]['path']
    raise SystemExit(f'{label} matches {len(rows)} sessions; narrow it or add --latest:\n'
                     + '   ' + '\n   '.join(format_rows(rows[:10])))


# ------------------------------------------------------------- commands ----

def format_rows(rows, full_id=False, width=64):
    now = time.time()
    lines = []
    for row in rows:
        session_id = row['id'] if full_id else short_id(row['id'])
        title = one_line(row['title'] or '(untitled)', width)
        cwd = row['cwd'] or '?'
        if row['cwd'] and not os.path.isdir(row['cwd']):
            cwd += '  [missing]'
        lines.append(f'{age(now - row["mtime"]):>4}  {session_id:<8}  {title:<{width}}  {cwd}')
    return lines


def cmd_list(args):
    rows = entries(args.store, args.cache or default_cache(args.store))
    if args.title:
        needle = args.title.lower()
        rows = [r for r in rows if needle in (r['title'] or '').lower()]
    if args.cwd:
        needle = args.cwd.lower()
        rows = [r for r in rows if needle in (r['cwd'] or '').lower()]
    if args.since:
        cutoff = time.time() - args.since * 86400
        rows = [r for r in rows if r['mtime'] >= cutoff]
    if args.sort == 'created':
        rows.sort(key=lambda r: r['createdAt'] or 0, reverse=not args.reverse)
    else:
        rows.sort(key=lambda r: r['mtime'], reverse=not args.reverse)
    shown = rows[:args.limit] if args.limit else rows
    print(f'{len(shown)} of {len(rows)} session(s)   (age, id, title, cwd)')
    print('\n'.join(format_rows(shown, args.full_id)))
    return 0


def cmd_search(args):
    rows = entries(args.store, args.cache or default_cache(args.store))
    if args.title:
        needle = args.title.lower()
        rows = [r for r in rows if needle in (r['title'] or '').lower()]
    if args.cwd:
        needle = args.cwd.lower()
        rows = [r for r in rows if needle in (r['cwd'] or '').lower()]
    if args.since:
        cutoff = time.time() - args.since * 86400
        rows = [r for r in rows if r['mtime'] >= cutoff]
    rows.sort(key=lambda r: r['mtime'], reverse=True)
    if args.max:
        rows = rows[:args.max]
    wanted = set(args.roles.split(',')) if args.roles else None
    pattern = re.compile(args.pattern, re.IGNORECASE)
    hits = scanned = 0
    started = time.time()
    for row in rows:
        if args.max_scan and scanned >= args.max_scan:
            print(f'note: stopped after {scanned} log(s) (--max-scan); narrow with '
                  f'--cwd/--title/--since', file=sys.stderr)
            break
        scanned += 1
        try:
            _header, events = load(row['path'])
        except SystemExit:
            continue
        for event in events:
            if not is_conversation(event):
                continue
            source = message_source(event)
            role = 'user' if event['type'] == 'user/message' else 'assistant'
            if event['type'] == 'user/message' and source not in (None, 'user'):
                continue
            if wanted is not None and role not in wanted:
                continue
            text = message_text(event).strip()
            found = pattern.search(text) if text else None
            if found is None:
                continue
            hits += 1
            start = max(0, found.start() - 60)
            print(f'{short_id(row["id"])}  {one_line(row["title"] or "(untitled)", 44)}')
            print(f'  [{event.get("seq")}] {event["type"].replace("/message", "")} :: '
                  f'…{one_line(text[start:found.start() + 140], 200)}…')
            if args.limit and hits >= args.limit:
                print(f'\n{scanned} log(s) scanned, {hits} hit(s), {time.time() - started:.1f}s')
                return 0
    print(f'\n{scanned} log(s) scanned, {hits} hit(s), {time.time() - started:.1f}s')
    return 0 if hits else 1


def cmd_header(args):
    path = pick(args)
    header, events = load(path)
    cwd = header.get('cwd')
    fields = {
        'file': path,
        'id': header.get('id'),
        'format': header.get('version'),
        'createdAt': header.get('createdAt'),
        'cwd': cwd,
        'cwd exists': 'yes' if cwd and os.path.isdir(cwd) else 'NO',
        'origin': header.get('origin') or 'main',
        'parentSession': header.get('parentSession'),
        'agentPreset': header.get('agentPreset'),
        'isSeeded': header.get('isSeeded'),
        'events': len(events),
        'bytes': os.path.getsize(path),
    }
    for key, value in fields.items():
        print(f'{key:12} {value}')
    if cwd and not os.path.isdir(cwd):
        print('warning      recorded cwd is missing: a turn cannot start until it is restored '
              '(see references/workdir-migration.md)')
    return 0


def summarize(event):
    kind = event.get('type')
    data = event.get('data') or {}
    if kind == 'turn/start':
        return f'turn={data.get("turn")}'
    if kind == 'turn/end':
        return f'turn={data.get("turn")} reason={(data.get("reason") or {}).get("kind")}'
    if kind in ('step/start', 'step/end'):
        return f'turn={data.get("turn")} step={data.get("step")}'
    if kind == 'tool/call':
        return f'{data.get("name")} id={data.get("id") or data.get("callId") or ""}'
    if kind == 'tool/result':
        return f'id={data.get("id") or data.get("callId") or ""}'
    if kind == 'session/title':
        return repr(data.get('title'))
    if kind == 'working-directory/change':
        return str(data.get('cwd'))
    if is_conversation(event):
        return f'{message_source(event) or "-"} :: {one_line(message_text(event), 110)}'
    return ''


def cmd_tail(args):
    path = pick(args)
    header, events = load(path)
    print(f'# {header.get("id")}  cwd={header.get("cwd")}  events={len(events)}')
    for event in events[-args.n:]:
        print(f'{event.get("seq"):>8}  {event.get("type"):<22} {summarize(event)}')
    open_turn = None
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
    path = pick(args)
    header, events = load(path)
    wanted = set(args.roles.split(',')) if args.roles else None
    pattern = re.compile(args.grep, re.IGNORECASE) if args.grep else None
    selected = []
    for event in events:
        if not is_conversation(event):
            continue
        source = message_source(event)
        role = 'user' if event['type'] == 'user/message' else 'assistant'
        injected = event['type'] == 'user/message' and source not in (None, 'user')
        if injected and not args.all:
            continue
        if wanted is not None and role not in wanted:
            continue
        text = message_text(event).strip()
        if not text:
            continue
        if pattern and not pattern.search(text):
            continue
        selected.append((event, source, text))
    if args.last:
        selected = selected[-args.limit:] if args.limit else selected[-5:]
    elif args.limit:
        selected = selected[:args.limit]
    if not selected:
        print('(no matching messages)')
        return 0
    print(f'# {header.get("id")}  {len(selected)} message(s) shown\n')
    for event, source, text in selected:
        tag = '' if source in (None, 'user') else f' ({source})'
        print(f'--- [{event.get("seq")}] {event["type"].replace("/message", "")}{tag}\n{text[:2000]}\n')
    return 0


def cmd_stats(args):
    path = pick(args)
    header, events = load(path)
    counts = {}
    for event in events:
        counts[event.get('type')] = counts.get(event.get('type'), 0) + 1
    packed = {'text-chunks', 'reasoning-chunks', 'tool-call-chunks'}
    ranges = []
    for event in events:
        if event.get('type') in packed and isinstance(event.get('seq0'), int):
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


# ------------------------------------------------------------------ CLI ----

def add_selector(p):
    p.add_argument('target', nargs='?', help='session id, log path, or session directory')
    p.add_argument('--latest', action='store_true', help='the most recently written session')
    p.add_argument('--title', help='match a substring of the cached session title')
    p.add_argument('--cwd', help='match a substring of the recorded working directory')
    p.add_argument('--store', default=STORE,
                   help='session store root (default: ~/.dsh/sessions)')
    p.add_argument('--cache',
                   help='projection-cache dir (default: <store>/../storages/session_projcache/sessions)')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    p = sub.add_parser('list', help='sessions you can see: age, id, title, cwd')
    p.add_argument('--title', help='match a substring of the title')
    p.add_argument('--cwd', help='match a substring of the working directory')
    p.add_argument('--since', type=float, help='only sessions written in the last N days')
    p.add_argument('--limit', type=int, default=25, help='0 = all')
    p.add_argument('--sort', choices=['mtime', 'created'], default='mtime')
    p.add_argument('--reverse', action='store_true', help='oldest first')
    p.add_argument('--full-id', action='store_true')
    p.add_argument('--store', default=STORE)
    p.add_argument('--cache')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('search', help='grep conversation text across sessions')
    p.add_argument('pattern', help='regular expression (case-insensitive)')
    p.add_argument('--cwd', help='cheap prefilter: working directory substring')
    p.add_argument('--title', help='cheap prefilter: title substring')
    p.add_argument('--since', type=float, help='only sessions written in the last N days')
    p.add_argument('--roles', help='user,assistant (default: both; injected context is always skipped)')
    p.add_argument('--limit', type=int, default=0, help='stop after N hits')
    p.add_argument('--max', type=int, default=0, help='only the N newest candidate sessions')
    p.add_argument('--max-scan', type=int, default=0, help='hard cap on logs scanned')
    p.add_argument('--store', default=STORE)
    p.add_argument('--cache')
    p.set_defaults(func=cmd_search)

    p = sub.add_parser('header', help='header fields, with a cwd-exists check')
    add_selector(p)
    p.set_defaults(func=cmd_header)

    p = sub.add_parser('tail', help='last N events, one line each')
    add_selector(p)
    p.add_argument('-n', type=int, default=15)
    p.set_defaults(func=cmd_tail)

    p = sub.add_parser('messages', help='conversation text (injected context filtered out)')
    add_selector(p)
    p.add_argument('--roles', help='user,assistant (default: human user + assistant)')
    p.add_argument('--last', action='store_true', help='the last N instead of the first N')
    p.add_argument('--limit', type=int, default=0, help='0 = all')
    p.add_argument('--grep', help='only messages matching this regex')
    p.add_argument('--all', action='store_true', help='include injected context messages')
    p.set_defaults(func=cmd_messages)

    p = sub.add_parser('stats', help='event-type histogram and seq range')
    add_selector(p)
    p.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
