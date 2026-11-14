# Scale baseline (partial — server side only, measured 2026-11-15)

Repo generated with `scripts/make_big_repo.py big1k 1000` (TypeScript, 3 imports/file).

| metric | big1k (1,000 files) |
|---|---|
| index time | 2.0 s |
| nodes / edges | 5,005 / 12,020 |
| module count | 5 |
| graph JSON (compact) | 4.91 MB |
| /graph overview body | ~3 KB, level=module, truncated=true, ~2 ms |

Not yet measured: 5,000/20,000-file repos, Unity load/build time, frame time
(needs Play mode; use JARVIS > Scale Test 5000 / 20000 menu items).
