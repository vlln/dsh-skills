#!/usr/bin/env python3
"""Rewrite stored DSH session working directories after a host directory rename.

For every `session*.jsonl.zstd` under --root:
  * the header line's `cwd` is remapped old-root -> new-root (when the target
    directory exists),
  * `working-directory/change` event payloads are remapped the same way.
Nothing else is touched: user/assistant/tool text is preserved verbatim.

Framing follows what the harness itself writes (see dsh-session-repair skill):
the header line in its own checksummed zstd frame, all events in a body frame.

Usage:
  migrate_cwd.py --root ~/.dsh/sessions --old /Users/vlln/Project --new /Users/vlln/Projects [--dry-run]
  migrate_cwd.py --root ~/.dsh/sessions --map-file mapping.json [--dry-run]

Exit codes: 0 ok, 2 error.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


def load_mapping(args):
    if args.map_file:
        with open(args.map_file) as f:
            pairs = json.load(f)
    else:
        pairs = [[args.old, args.new]]
    # longest old prefix first so nested mappings win
    pairs = sorted(pairs, key=lambda p: len(p[0]), reverse=True)
    resolved = []
    for old, new in pairs:
        if not os.path.isdir(new):
            print(f'FATAL: mapping target does not exist: {new}', file=sys.stderr)
            sys.exit(2)
        resolved.append((old.rstrip('/'), new.rstrip('/')))
    return resolved


def map_path(path, mapping):
    if not isinstance(path, str) or not path:
        return None
    for old, new in mapping:
        if path == old:
            return new
        if path.startswith(old + '/'):
            return new + path[len(old):]
    return None


def zstd_decompress(path):
    proc = subprocess.run(['zstd', '-dc', '-q', path], capture_output=True)
    if proc.returncode != 0:
        raise IOError(proc.stderr.decode('utf-8', 'replace')[:300])
    return proc.stdout


def encode_frames(text, tmpdir):
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if not lines:
        raise ValueError('empty log')
    hdr_path = os.path.join(tmpdir, 'hdr')
    with open(hdr_path, 'w') as f:
        f.write(lines[0] + '\n')
    out = subprocess.run(['zstd', '-q', '-c', '--check', hdr_path], capture_output=True, check=True).stdout
    if len(lines) > 1:
        body_path = os.path.join(tmpdir, 'body')
        with open(body_path, 'w') as f:
            f.write('\n'.join(lines[1:]) + '\n')
        out += subprocess.run(['zstd', '-q', '-c', '--check', body_path], capture_output=True, check=True).stdout
    return out


def is_live(lock_path):
    try:
        fd = os.open(lock_path, os.O_RDWR)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def transform(text, mapping):
    lines = text.split('\n')
    if not lines or not lines[0].strip():
        raise ValueError('missing header line')
    header = json.loads(lines[0])
    old_cwd = header.get('cwd')
    new_cwd = map_path(old_cwd, mapping)
    changes = []
    missing = []
    if new_cwd and new_cwd != old_cwd and not os.path.isdir(new_cwd):
        missing.append(new_cwd)
        new_cwd = None
    if new_cwd and new_cwd != old_cwd:
        needle = '"cwd":' + json.dumps(old_cwd, ensure_ascii=False)
        if needle not in lines[0]:
            raise ValueError('header cwd field not found literally')
        lines[0] = lines[0].replace(needle, '"cwd":' + json.dumps(new_cwd, ensure_ascii=False), 1)
        changes.append(('header', old_cwd, new_cwd))
    for i in range(1, len(lines)):
        line = lines[i]
        if 'working-directory/change' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') != 'working-directory/change':
            continue
        cur = (event.get('data') or {}).get('cwd')
        nxt = map_path(cur, mapping)
        if nxt and nxt != cur:
            needle = '"cwd":' + json.dumps(cur, ensure_ascii=False)
            if needle not in line:
                raise ValueError('change-event cwd field not found literally')
            lines[i] = line.replace(needle, '"cwd":' + json.dumps(nxt, ensure_ascii=False), 1)
            changes.append((f'change@line{i}', cur, nxt))
    return '\n'.join(lines), header.get('id'), changes, missing


def migrate_file(path, mapping, dry_run, force_live=False):
    result = {'path': path, 'status': 'skip'}
    lock_path = os.path.join(os.path.dirname(path), 'session.lock')
    if not force_live and os.path.exists(lock_path) and is_live(lock_path):
        result['status'] = 'live-skipped'
        return result
    raw = zstd_decompress(path)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        result['status'] = 'non-utf8-skipped'
        return result
    new_text, session_id, changes, missing = transform(text, mapping)
    result['id'] = session_id
    if missing:
        result['status'] = 'missing-target'
        result['missing'] = missing
        return result
    if not changes:
        result['status'] = 'unchanged'
        return result
    result['changes'] = changes
    result['status'] = 'dry-run' if dry_run else 'rewritten'
    if dry_run:
        return result
    expected = new_text.encode('utf-8')
    with tempfile.TemporaryDirectory(dir=os.path.dirname(path)) as tmpdir:
        payload = encode_frames(new_text, tmpdir)
    # verify the produced bytes decode back to exactly the intended text
    tmp_out = path + f'.migrate-{os.getpid()}'
    with open(tmp_out, 'wb') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp_out, 0o600)
    back = zstd_decompress(tmp_out)
    if back != expected:
        os.unlink(tmp_out)
        result['status'] = 'verify-failed'
        return result
    os.replace(tmp_out, path)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--old')
    ap.add_argument('--new')
    ap.add_argument('--map-file')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--manifest')
    ap.add_argument('--force-live', action='store_true', help='migrate even when a client holds the session lock')
    args = ap.parse_args()
    if not args.map_file and not (args.old and args.new):
        ap.error('need --old/--new or --map-file')
    mapping = load_mapping(args)
    print('mapping: ' + ', '.join(f'{o} -> {n}' for o, n in mapping))

    files = []
    for dirpath, _dirnames, filenames in os.walk(args.root):
        for name in filenames:
            if name.startswith('session') and name.endswith('.jsonl.zstd'):
                files.append(os.path.join(dirpath, name))
    files.sort()
    print(f'{len(files)} log(s) under {args.root}')

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for res in pool.map(lambda p: migrate_file(p, mapping, args.dry_run, args.force_live), files):
            results.append(res)
            if res['status'] not in ('unchanged',):
                print(f"{res['status']:<14} {res.get('id', '?')}  {res['path']}")
                for kind, old, new in res.get('changes', []):
                    print(f'               {kind}: {old} -> {new}')

    summary = {}
    for res in results:
        summary[res['status']] = summary.get(res['status'], 0) + 1
    print('summary: ' + json.dumps(summary, sort_keys=True))
    if args.manifest:
        with open(args.manifest, 'w') as f:
            json.dump(results, f, indent=1)
        print(f'manifest: {args.manifest}')
    if any(res['status'] in ('verify-failed',) for res in results):
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
