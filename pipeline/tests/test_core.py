import pytest

from pipeline.core import (parse_source, build_index, module_index, resolve_import,
                           extract_mentions, parse_patch, radius_metrics,
                           bfs_ranking, bm25_ranking, recall_at)
from pipeline.run import summarize


def index(sources):
    files = {p: parse_source(s) for p, s in sources.items()}
    return files, *build_index(files)


def test_relative_import():
    files, graph, _, _ = index({'pkg/__init__.py': '', 'pkg/a.py': 'from . import b', 'pkg/b.py': ''})
    assert 'pkg/b.py' in graph['pkg/a.py']
    assert 'pkg/a.py' in graph['pkg/b.py']


def test_parent_relative_import():
    modules = module_index(['pkg/a.py', 'pkg/sub/b.py'])
    assert resolve_import('pkg/sub/b.py', 'a', 2, ['Thing'], modules) == {'pkg/a.py'}
    assert resolve_import('pkg/sub/b.py', 'a', 5, [], modules) == set()


def test_absolute_and_src_imports():
    _, graph, _, _ = index({'src/pkg/a.py': 'from pkg.b import Thing\nimport os', 'src/pkg/b.py': 'class Thing: pass'})
    assert graph['src/pkg/a.py'] == {'src/pkg/b.py'}


def test_package_import():
    _, graph, _, _ = index({'pkg/__init__.py': 'from .child import hello', 'pkg/child.py': 'def hello(): pass', 'app.py': 'import pkg'})
    assert graph['pkg/__init__.py'] == {'pkg/child.py', 'app.py'}


def test_unparseable_file_is_safe():
    parsed = parse_source('print "python2"')
    assert not parsed.parsed and not parsed.symbols and parsed.chars > 0


def test_method_and_async_index():
    _, _, symbols, _ = index({'a.py': 'class Thing:\n    async def run(self): pass\n'})
    assert symbols['Thing.run'] == {'a.py'}
    assert symbols['run'] == {'a.py'}


def test_mentions_paths_dotted_backticks_traceback():
    files, _, symbols, modules = index({'pkg/a.py': 'def solve(): pass', 'pkg/b.py': 'class Error: pass'})
    result = extract_mentions('In pkg/a.py and pkg.b, `solve` fails.\n  File "/tmp/pkg/a.py", line 4, in solve\n', list(files), symbols, modules)
    found = {m['text']: m['files'] for m in result}
    assert found['pkg/a.py'] == ['pkg/a.py']
    assert found['pkg.b'] == ['pkg/b.py']
    assert found['solve'] == ['pkg/a.py']
    assert found['tmp/pkg/a.py'] == ['pkg/a.py']


def test_mentions_ambiguity_and_unresolved():
    files, _, symbols, modules = index({'one/a.py': 'def run(): pass', 'two/a.py': 'def run(): pass'})
    mentions = extract_mentions('`run` `run` a.py missing.py', list(files), symbols, modules)
    assert next(m for m in mentions if m['text'] == 'run')['files'] == ['one/a.py', 'two/a.py']
    assert next(m for m in mentions if m['text'] == 'missing.py')['files'] == []
    assert len(mentions) == 3


def test_plain_words_do_not_resolve_symbols():
    files, _, symbols, modules = index({'a.py': 'def run(): pass'})
    assert extract_mentions('Please run this example', list(files), symbols, modules) == []


def test_patch_function_ranges_and_hunk_context():
    files = {'a.py': parse_source('class A:\n    def run(self):\n        return 1\n')}
    patch = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@ class A:\n class A:\n     def run(self):\n-        return 1\n+        return 2\n'
    result = parse_patch(patch, files)
    assert result[0]['functions'] == ['A.run']
    assert result[0]['hunk_contexts'] == ['class A:']


def test_patch_new_and_deleted_files():
    patch = 'diff --git a/new.py b/new.py\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+def fresh(): pass\ndiff --git a/old.py b/old.py\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-def old(): pass'
    result = parse_patch(patch, {'old.py': parse_source('def old(): pass')})
    assert result[0]['added_definitions'] == ['fresh']
    assert result[0]['functions'] == []
    assert result[1]['file'] == 'old.py' and result[1]['functions'] == ['old']


def test_bfs_path_and_inclusive_budget():
    graph = {'a': {'b'}, 'b': {'a', 'c'}, 'c': {'b'}}
    metrics, ranking = radius_metrics(graph, ['a'], ['c'], {'a': 4, 'b': 8, 'c': 12})
    assert ranking == ['a', 'b', 'c']
    assert metrics['radius'] == 2 and metrics['hop_path'] == ranking
    assert metrics['context_budget_tokens'] == 6


def test_direct_and_multisource_bfs():
    graph = {'a': {'b'}, 'b': {'a'}, 'c': set()}
    metrics, _ = radius_metrics(graph, ['c', 'b'], ['b'], dict.fromkeys(graph, 4))
    assert metrics['radius'] == 0 and metrics['hop_path'] == ['b']
    assert metrics['context_budget_tokens'] == 1


@pytest.mark.parametrize('seeds,status,budget', [([], 'no_mentions', None), (['a'], 'unreachable', 1)])
def test_missing_and_unreachable(seeds, status, budget):
    metrics, _ = radius_metrics({'a': set(), 'b': set()}, seeds, ['b'], {'a': 4, 'b': 4})
    assert metrics['radius'] is None and metrics['radius_status'] == status
    assert metrics['context_budget_tokens'] == budget and metrics['hop_path'] == []


def test_bfs_ties_and_cycles_are_deterministic():
    graph = {'c': {'b', 'a'}, 'b': {'a', 'c'}, 'a': {'b', 'c'}}
    assert bfs_ranking(graph, ['c'])[0] == ['c', 'a', 'b']


def test_bm25_identifies_path_and_symbols():
    files = {'misc.py': parse_source('def unrelated(): pass'), 'math/matrix.py': parse_source('def invertMatrix(): pass')}
    assert bm25_ranking(files, 'invert matrix error')[0] == 'math/matrix.py'
    assert bm25_ranking(files, '') == ['math/matrix.py', 'misc.py']
    assert bm25_ranking({}, 'x') == []


def test_recall_counts_files_not_hit_rate():
    assert recall_at(['a', 'b'], ['a', 'c'], 1) == .5
    assert recall_at([], ['a'], 10) == 0
    assert recall_at(['a'], [], 1) == 0


def test_macro_summary_and_null_bucket():
    record = {'repo': 'a/b', 'resolved_mentions': 1, 'radius': 0, 'radius_status': 'reached', 'context_budget_tokens': 12,
              'baselines': {b: {f'recall@{k}': .5 for k in (1, 5, 10)} for b in ('bfs', 'bm25')}}
    summary = summarize([record])
    assert summary['radius_histogram'] == {'0': 1}
    assert summary['baselines']['bfs']['recall@1'] == .5
