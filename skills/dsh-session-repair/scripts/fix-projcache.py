#!/usr/bin/env python3
"""Re-point the projection-cache checkpoint identities after a cwd migration.

`~/.dsh/storages/session_projcache` binds every cached checkpoint to the
session's immutable header identity — including `cwd`. A header cwd rewrite
therefore invalidates ALL cached rows, and the sidebar (which reads titles from
this cache and never from the logs) shows every session as untitled until each
one is opened and re-folded. Rewriting the cached `identity.cwd` with the same
mapping keeps every checkpoint valid, so titles come back without a re-fold.

The log itself keeps `session/title` events; this only repairs the list hint.
"""
import argparse
import glob
import json
import os
import sys


def load_mapping(path):
    pairs = sorted(([o.rstrip('/'), n.rstrip('/')] for o, n in json.load(open(path))),
                   key=lambda p: len(p[0]), reverse=True)
    return pairs


def map_path(path, mapping):
    if not isinstance(path, str):
        return None
    for old, new in mapping:
        if path == old:
            return new
        if path.startswith(old + '/'):
            return new + path[len(old):]
    return None


def write_json_atomic(path, doc):
    tmp = path + f'.fix-{os.getpid()}'
    with open(tmp, 'w') as f:
        json.dump(doc, f, ensure_ascii=True, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map-file', required=True)
    ap.add_argument('--storages', default=os.path.expanduser('~/.dsh/storages'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    mapping = load_mapping(args.map_file)

    changed, unchanged, unreadable, missing = [], [], [], []
    targets = sorted(glob.glob(os.path.join(args.storages, 'session_projcache', 'sessions', '*.json')))
    for path in targets:
        try:
            doc = json.load(open(path))
        except (ValueError, OSError):
            unreadable.append(path)
            continue
        record = doc.get('record') or {}
        identity = record.get('identity') or {}
        old = identity.get('cwd')
        new = map_path(old, mapping)
        if new is None or new == old:
            unchanged.append(path)
            continue
        if not os.path.isdir(new):
            missing.append((path, new))
            continue
        identity['cwd'] = new
        changed.append((path, old, new))
        if not args.dry_run:
            write_json_atomic(path, doc)

    legacy = os.path.join(args.storages, 'session_projcache.json')
    legacy_changed = 0
    if os.path.exists(legacy):
        doc = json.load(open(legacy))
        for sid, rec in (doc.get('tables') or {}).get('sessions', {}).items():
            identity = rec.get('identity') or {}
            old = identity.get('cwd')
            new = map_path(old, mapping)
            if new and new != old and os.path.isdir(new):
                identity['cwd'] = new
                legacy_changed += 1
                changed.append((f'{legacy}:{sid}', old, new))
        if legacy_changed and not args.dry_run:
            write_json_atomic(legacy, doc)

    for path, old, new in changed:
        print(f'{"DRY " if args.dry_run else ""}{os.path.basename(path)}: {old} -> {new}')
    for path, new in missing:
        print(f'MISSING-TARGET {path}: {new}')
    print(f'summary: changed={len(changed) - (0 if args.dry_run else 0)} '
          f'(per-record={len(changed) - legacy_changed}, legacy-file={legacy_changed}), '
          f'unchanged={len(unchanged)}, unreadable={len(unreadable)}, missing-target={len(missing)}')
    if unreadable:
        for path in unreadable:
            print(f'unreadable: {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
