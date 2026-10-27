"""Release checks: recompute invariants from committed records, no network."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ATLAS = json.loads((ROOT / 'data/atlas.json').read_text())


def test_complete_release_and_source_identity():
    records = ATLAS['instances']
    assert len(records) == ATLAS['overall']['instances'] == 300
    assert len({r['instance_id'] for r in records}) == 300
    assert len({r['repo'] for r in records}) == ATLAS['overall']['repos'] == 12
    assert sum(r['instances'] for r in ATLAS['repos']) == 300
    assert ATLAS['run']['elapsed_seconds'] < 3600
    digest = hashlib.sha256((ROOT / 'pipeline/core.py').read_bytes() + (ROOT / 'pipeline/run.py').read_bytes()).hexdigest()
    assert ATLAS['run']['pipeline_sha256'] == digest


def test_radius_paths_and_null_semantics():
    for record in ATLAS['instances']:
        path = record['hop_path']
        if record['radius'] is not None:
            assert len(path) == record['radius'] + 1
            assert path[0] in record['mentioned_files']
            assert path[-1] in record['edited_files']
            assert record['radius_status'] == 'reached'
            assert record['context_budget_tokens'] >= 0
            assert len(set(path)) == len(path)
        else:
            assert not path
            if record['radius_status'] == 'no_mentions':
                assert not record['mentioned_files']
                assert record['context_budget_tokens'] is None
            else:
                assert record['radius_status'] == 'unreachable'
                assert record['mentioned_files']
                assert record['visited_files'] == record['reachable_files']


def test_mention_counts_and_excerpts():
    for record in ATLAS['instances']:
        assert len(record['issue_excerpt']) <= 300
        assert len(record['mentions']) == record['mention_count']
        assert len({m['text'] for m in record['mentions']}) == record['mention_count']
        assert sum(bool(m['files']) for m in record['mentions']) == record['resolved_mentions']
        assert sorted({p for m in record['mentions'] for p in m['files']}) == record['mentioned_files']
        assert record['unparsable_files'] <= record['repo_py_files']
        assert record['visited_files'] <= record['reachable_files'] <= record['repo_py_files']


def test_recall_recomputed_from_published_rankings():
    for baseline in ('bfs', 'bm25'):
        for k in (1, 5, 10):
            values = []
            for record in ATLAS['instances']:
                gold = set(record['edited_files'])
                ranked = record['baselines'][baseline]['top_files']
                assert len(ranked) == len(set(ranked))
                assert len(ranked) <= 10
                value = len(set(ranked[:k]) & gold) / len(gold)
                assert record['baselines'][baseline][f'recall@{k}'] == value
                values.append(value)
            assert ATLAS['overall']['baselines'][baseline][f'recall@{k}'] == pytest.approx(sum(values) / len(values))


def test_histograms_match_records_and_repository_slices():
    for summary in [ATLAS['overall'], *ATLAS['repos']]:
        records = [r for r in ATLAS['instances'] if 'repo' not in summary or r['repo'] == summary['repo']]
        histogram = {}
        for record in records:
            key = str(record['radius']) if record['radius'] is not None else 'null'
            histogram[key] = histogram.get(key, 0) + 1
        assert summary['radius_histogram'] == histogram
        assert summary['direct_instances'] == histogram.get('0', 0)
        assert summary['reached_instances'] + summary['no_mention_instances'] + summary['unreachable_instances'] == len(records)
