#!/usr/bin/env python3
"""Re-point durable GUI workspace records after the host directory rename.

Workspace records store a canonical `path`; the registry matches sessions by
their header cwd. After a cwd migration the old records must follow, otherwise
every session drops out of the sidebar at the next boot. A mapped path that
collides with an existing workspace (two records cannot own one canonical path)
is merged into that workspace and its record removed.
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.expanduser('~/.dsh/storages/workspace.json')


def map_path(path, mapping):
    for old, new in mapping:
        if path == old:
            return new
        if path.startswith(old + '/'):
            return new + path[len(old):]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map-file', required=True)
    ap.add_argument('--path', default=ROOT)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    mapping = sorted(([o.rstrip('/'), n.rstrip('/')] for o, n in json.load(open(args.map_file))),
                     key=lambda p: len(p[0]), reverse=True)

    with open(args.path) as f:
        doc = json.load(f)
    tables = doc['tables']['workspaces']
    order = doc['global']['workspaceIds']

    by_path = {}
    for wid, rec in tables.items():
        by_path.setdefault(rec['path'], []).append(wid)

    changes = []
    removals = []
    for wid in list(order):
        rec = tables[wid]
        target = map_path(rec['path'], mapping)
        if target is None or target == rec['path']:
            continue
        if not os.path.isdir(target):
            print(f'NO-TARGET {wid} {rec["path"]} -> {target}')
            continue
        holders = [h for h in by_path.get(target, []) if h != wid]
        if holders:
            keeper = holders[0]
            print(f'MERGE {wid} ({rec["path"]}) into {keeper} ({target}); '
                  f'{len(rec.get("sessionIds", []))} session id(s) carried over')
            keep = tables[keeper]
            for sid in rec.get('sessionIds', []):
                if sid not in keep.setdefault('sessionIds', []):
                    keep['sessionIds'].append(sid)
            removals.append(wid)
            changes.append(('merge', wid, keeper, rec['path'], target))
        else:
            old_path = rec['path']
            old_title = rec.get('title')
            rec['path'] = target
            # A workspace whose title is still the old folder's basename was auto-derived;
            # let it follow the rename, otherwise it keeps pointing at a name that is gone.
            if old_title == os.path.basename(old_path):
                rec['title'] = os.path.basename(target)
                print(f'REPOINT {wid}: {old_path} -> {target}  (title {old_title!r} -> '
                      f'{rec["title"]!r})')
            else:
                print(f'REPOINT {wid}: {old_path} -> {target}')
            by_path.setdefault(target, []).append(wid)
            changes.append(('repoint', wid, None, old_path, target))

    for wid in removals:
        tables.pop(wid, None)
        while wid in order:
            order.remove(wid)

    if args.dry_run:
        print(f'dry-run: {len(changes)} change(s), {len(removals)} record(s) removed')
        return 0

    backup = args.path + '.pre-cwd-migration'
    if not os.path.exists(backup):
        shutil.copy2(args.path, backup)
        print(f'backup: {backup}')
    tmp = args.path + '.tmp-write'
    with open(tmp, 'w') as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, args.path)
    print(f'wrote {args.path}: {len(changes)} change(s), {len(removals)} record(s) removed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
