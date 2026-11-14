#!/usr/bin/env python3
'''python scripts/make_big_repo.py NAME N_FILES  ->  repository/NAME with N_FILES TypeScript files'''
import os, random, sys
from pathlib import Path

name, n = sys.argv[1], int(sys.argv[2])
root = Path(__file__).resolve().parent.parent / 'repository' / name
rnd = random.Random(7)
pkgs = ['pkg%02d' % i for i in range(max(5, n // 200))]
files = ['%s/mod%02d/file%05d.ts' % (pkgs[i % len(pkgs)], (i // len(pkgs)) % 10, i) for i in range(n)]
for i, f in enumerate(files):
    out = []
    imps = rnd.sample(range(n), 3)
    for j in imps:
        rel = os.path.relpath(files[j][:-3], os.path.dirname(f)).replace(os.sep, '/')
        rel = rel if rel.startswith('.') else './' + rel
        out.append('import { fn%d_0 } from %r;' % (j, rel))
    for k in range(4):
        call = 'fn%d_%d()' % (i, k + 1) if k < 3 else 'fn%d_0()' % imps[0]
        out.append('export function fn%d_%d() { return %s; }' % (i, k, call))
    p = root / f
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(chr(10).join(out) + chr(10))
print('wrote', n, 'files to', root)
