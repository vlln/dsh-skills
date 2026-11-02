#!/usr/bin/env python3
"""Re-key DSH session directories after a working-directory migration.

The session store derives a project directory from the header cwd
(`projectKey` in @deepseek-ai/dsh-session-persistence-jsonl). Rewriting a
header cwd without moving its directory leaves the log under a stale,
human-confusing key, and any later session created in the new path gets a
second directory for the same project. This moves each session directory
under the key its header now names, merges into an existing key directory,
and drops the emptied project directory.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

SAFE = re.compile(r'^[A-Za-z0-9._-]$')


def encode_segment(raw):
    if raw == '.':
        return '~002E'
    if raw == '..':
        return '~002E~002E'
    out = []
    for ch in raw:
        out.append(ch if (SAFE.match(ch) and ch != '~') else '~%04X' % ord(ch))
    return ''.join(out)


def project_key(cwd):
    readable = ''
    sep_run = False
    for ch in cwd:
        if ch in '/\\:':
            if not sep_run:
                readable += '-'
            sep_run = True
        elif SAFE.match(ch) and ch != '~':
            readable += ch
            sep_run = False
        else:
            readable += '~%04X' % ord(ch)
            sep_run = False
    readable = re.sub(r'^-+', '', readable) or 'root'
    return '--' + readable[:251] + '--'


def log_path(session_dir):
    for name in ('session.v4.jsonl.zstd', 'session.jsonl.zstd'):
        p = os.path.join(session_dir, name)
        if os.path.exists(p):
            return p
    for name in sorted(os.listdir(session_dir)):
        if name.startswith('session') and name.endswith('.jsonl.zstd'):
            return os.path.join(session_dir, name)
    return None


def header_cwd(path):
    proc = subprocess.Popen(['zstd', '-dc', '-q', path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        line = proc.stdout.readline().decode('utf-8', 'replace')
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()
    import json
    try:
        return json.loads(line).get('cwd')
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    root = args.root

    moves, skipped, planned_dirs = [], [], []
    for project in sorted(os.listdir(root)):
        pdir = os.path.join(root, project)
        if not os.path.isdir(pdir) or not project.startswith('--'):
            continue
        entries = sorted(e for e in os.listdir(pdir) if os.path.isdir(os.path.join(pdir, e)))
        for entry in entries:
            sdir = os.path.join(pdir, entry)
            lp = log_path(sdir)
            if lp is None:
                skipped.append((sdir, 'no-log'))
                continue
            cwd = header_cwd(lp)
            if not cwd or not os.path.isabs(cwd):
                skipped.append((sdir, 'no-cwd'))
                continue
            want = project_key(cwd)
            if want == project:
                continue
            dst = os.path.join(root, want, entry)
            if os.path.exists(dst):
                skipped.append((sdir, f'target-exists:{dst}'))
                continue
            moves.append((sdir, dst, cwd))
            planned_dirs.append(pdir)

    print(f'{len(moves)} session dir(s) to re-key')
    for sdir, dst, cwd in moves:
        print(f'  {os.path.basename(os.path.dirname(sdir))}/{os.path.basename(sdir)}')
        print(f'    cwd {cwd} -> {os.path.basename(os.path.dirname(dst))}/')
    for sdir, why in skipped:
        print(f'  SKIP {sdir}: {why}')
    if args.dry_run:
        return 0
    for sdir, dst, cwd in moves:
        os.makedirs(os.path.dirname(dst), mode=0o700, exist_ok=True)
        os.rename(sdir, dst)
    # drop emptied project dirs
    for pdir in sorted(set(planned_dirs)):
        try:
            if not os.listdir(pdir):
                os.rmdir(pdir)
                print(f'removed empty project dir {os.path.basename(pdir)}')
        except OSError as exc:
            print(f'left {pdir}: {exc}')
    print(f'moved {len(moves)} session dir(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
