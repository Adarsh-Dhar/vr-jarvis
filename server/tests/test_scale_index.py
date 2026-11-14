"""Scale tests: file discovery pruning, MAX_FILES cap, fast indexing of ~1500 files,
and the file-level import linking rules (exact base-name match, inferred on ties)."""
import time
from pathlib import Path

from ai_agents import config
from ai_agents.intelligence.graph_engine import store, indexer


def make_repo(root: Path, n: int):
    for i in range(n):
        d = root / ('pkg%d' % (i % 10))
        d.mkdir(parents=True, exist_ok=True)
        j = (i + 1) % n
        lines = ['import { g%d } from %r;' % (j, '../pkg%d/f%d' % (j % 10, j)),
                 'export function g%d() { return g%d(); }' % (i, j)]
        (d / ('f%d.ts' % i)).write_text(chr(10).join(lines) + chr(10))


def test_source_files_prunes_node_modules(tmp_path):
    (tmp_path / 'a.ts').write_text('export const a = 1;')
    junk = tmp_path / 'node_modules' / 'x'
    junk.mkdir(parents=True)
    for i in range(300):
        (junk / ('m%d.ts' % i)).write_text('export const m = 1;')
    assert [r for _, r in store._source_files(tmp_path)] == ['a.ts']


def test_max_files_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'MAX_FILES', 5)
    make_repo(tmp_path, 20)
    assert len(list(store._source_files(tmp_path))) == 5


def test_index_1500_files_is_fast_and_links_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'REPOSITORY_DIR', tmp_path)
    make_repo(tmp_path / 'big', 1500)
    t0 = time.time()
    g = indexer.index_repo('big')
    assert time.time() - t0 < 60          # tighten after the baseline
    ids = {n['id'] for n in g['nodes']}
    imp = [e for e in g['edges'] if e.get('type') == 'imports' and e['src'].startswith('file::')]
    assert len(imp) >= 1400
    assert all(e['src'] in ids and e['dst'] in ids for e in imp)


def _link_graph(tmp_path, monkeypatch, files):
    """Index a tiny repo and return its file->file 'imports' edges."""
    monkeypatch.setattr(config, 'REPOSITORY_DIR', tmp_path)
    root = tmp_path / 'linkrepo'
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    g = indexer.index_repo('linkrepo')
    return [e for e in g['edges']
            if e.get('type') == 'imports' and e['src'].startswith('file::')]


def test_import_link_ambiguous_base_is_inferred_and_nearest(tmp_path, monkeypatch):
    edges = _link_graph(tmp_path, monkeypatch, {
        'a/util.ts': 'export const u = 1;\n',
        'b/util.ts': 'export const u = 2;\n',
        'a/main.ts': "import { u } from './util';\nexport const m = u;\n",
    })
    hit = [e for e in edges if e['src'] == 'file::a/main.ts']
    assert len(hit) == 1
    assert hit[0]['dst'] == 'file::a/util.ts'
    assert hit[0]['kind'] == 'inferred'


def test_import_link_unique_name_is_confirmed(tmp_path, monkeypatch):
    edges = _link_graph(tmp_path, monkeypatch, {
        'lib/thing.ts': 'export const t = 1;\n',
        'app/main.ts': "import { t } from '../lib/thing';\nexport const m = t;\n",
    })
    hit = [e for e in edges if e['src'] == 'file::app/main.ts']
    assert len(hit) == 1
    assert hit[0]['dst'] == 'file::lib/thing.ts'
    assert hit[0]['kind'] == 'confirmed'


def test_import_link_no_substring_match(tmp_path, monkeypatch):
    # 'auth' must not link to data/author.ts: matching is on the base name, not substrings.
    edges = _link_graph(tmp_path, monkeypatch, {
        'data/author.ts': 'export const a = 1;\n',
        'svc/main.ts': "import { x } from './auth';\nexport const m = x;\n",
    })
    assert not [e for e in edges if e['src'] == 'file::svc/main.ts' and 'author' in e['dst']]


def test_import_link_folder_resolves_to_index(tmp_path, monkeypatch):
    edges = _link_graph(tmp_path, monkeypatch, {
        'pkg/mod/index.ts': 'export const i = 1;\n',
        'app/main.ts': "import { i } from '../pkg/mod';\nexport const m = i;\n",
    })
    hit = [e for e in edges if e['src'] == 'file::app/main.ts']
    assert len(hit) == 1
    assert hit[0]['dst'] == 'file::pkg/mod/index.ts'
