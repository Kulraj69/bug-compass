from rerank import annotations, build_prompt, parse, pool
from evaluate import mentions_first, recall

TASK = {
    "instance_id": "x__y-1", "repo": "x/y", "problem_statement": "`foo` breaks in a/b.py",
    "mentions": [{"text": "foo", "kind": "symbol", "files": ["a/b.py"]}],
    "edited_files": ["a/secret_gold.py"],
    "baselines": {"bfs": {"top_files": ["a/b.py", "a/c.py"]}, "bm25": {"top_files": ["a/c.py", "a/d.py"]}},
}


def test_pool_is_sorted_union_without_gold():
    assert pool(TASK) == ["a/b.py", "a/c.py", "a/d.py"]


def test_prompts_never_contain_gold():
    for cond in ("plain", "compass"):
        assert "secret_gold" not in build_prompt(TASK, cond)


def test_compass_annotations():
    ann = annotations(TASK)
    assert "issue names `foo`" in ann["a/b.py"]
    assert ann["a/c.py"] == "text-match rank 1"


def test_parse_filters_to_candidates_and_dedupes():
    text = '```json\n["a/c.py", "zz.py", "a/c.py", "a/b.py"]\n```'
    assert parse(text, pool(TASK)) == ["a/c.py", "a/b.py"]
    assert parse("I think a/d.py", pool(TASK)) == ["a/d.py"]
    assert parse("no idea", pool(TASK)) == []


def test_mentions_first_and_recall():
    assert mentions_first(TASK)[0] == "a/b.py"
    assert recall(["a/b.py", "a/x.py"], ["a/x.py", "a/y.py"], 2) == 0.5
