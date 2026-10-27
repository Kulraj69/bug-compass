"""Score Gemma 4 rerank runs against the Bug Compass baselines.

Recall@k matches the atlas definition: |top-k ∩ edited| / |edited|, averaged
over tasks. Gold edits are used only here, never in prompts or candidate pools.
Writes results/summary.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from rerank import ROOT, pool

HERE = Path(__file__).parent


def recall(ranking: list[str], edited: list[str], k: int) -> float:
    gold = set(edited)
    return len(set(ranking[:k]) & gold) / len(gold) if gold else 0.0


def mentions_first(task: dict) -> list[str]:
    """Non-LLM control using the same signals as the compass prompt."""
    files = pool(task)
    mentioned = {f for m in task["mentions"] for f in m["files"]}
    bm25 = task["baselines"]["bm25"]["top_files"]
    key = lambda f: (f not in mentioned, bm25.index(f) if f in bm25 else 99, f)
    return sorted(files, key=key)


def load(cond: str) -> dict[str, dict]:
    p = HERE / "results" / f"{cond}.jsonl"
    return {json.loads(l)["instance_id"]: json.loads(l) for l in p.open()} if p.exists() else {}


def bootstrap_diff(a: list[float], b: list[float], n: int = 10000, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    m = len(a)
    diffs = sorted(
        sum(a[i] - b[i] for i in idx) / m
        for idx in ([rng.randrange(m) for _ in range(m)] for _ in range(n))
    )
    return [round(diffs[int(0.025 * n)], 4), round(diffs[int(0.975 * n)], 4)]


def main() -> None:
    tasks = {t["instance_id"]: t for t in json.load(open(ROOT / "data/atlas.json"))["instances"]}
    runs = {c: load(c) for c in ("plain", "compass")}
    ids = sorted(set(tasks).intersection(*[set(r) for r in runs.values() if r]) if any(runs.values()) else [])
    rankers = {
        "bm25": lambda t: t["baselines"]["bm25"]["top_files"],
        "bfs": lambda t: t["baselines"]["bfs"]["top_files"],
        "mentions_first": mentions_first,
    }
    for c, r in runs.items():
        if r:
            rankers[f"gemma4_{c}"] = lambda t, r=r: r[t["instance_id"]]["ranking"]
    per = {name: {k: [recall(f(tasks[i]), tasks[i]["edited_files"], k) for i in ids] for k in (1, 5)}
           for name, f in rankers.items()}
    summary = {
        "tasks": len(ids),
        "pool_mean_size": round(sum(len(pool(tasks[i])) for i in ids) / len(ids), 2),
        "pool_oracle_recall": round(sum(recall(pool(tasks[i]), tasks[i]["edited_files"], 99) for i in ids) / len(ids), 4),
        "recall": {n: {f"@{k}": round(sum(v) / len(v), 4) for k, v in d.items()} for n, d in per.items()},
        "paired_bootstrap_95ci": {},
        "gemma_runs": {},
    }
    for c, r in runs.items():
        if not r:
            continue
        name = f"gemma4_{c}"
        for base in ("bm25", "mentions_first") + (("gemma4_plain",) if c == "compass" and runs["plain"] else ()):
            for k in (1, 5):
                summary["paired_bootstrap_95ci"][f"{name}-{base}@{k}"] = bootstrap_diff(per[name][k], per[base][k])
        rows = [r[i] for i in ids]
        summary["gemma_runs"][name] = {
            "empty_rankings": sum(not x["ranking"] for x in rows),
            "mean_seconds": round(sum(x["seconds"] for x in rows) / len(rows), 2),
            "mean_prompt_tokens": round(sum(x["usage"].get("prompt_tokens", 0) for x in rows) / len(rows), 1),
            "total_seconds": round(sum(x["seconds"] for x in rows), 1),
        }
    slices = {
        "direct_mention (radius 0)": [i for i in ids if tasks[i]["radius"] == 0],
        "reached_via_imports (radius>=1)": [i for i in ids if (tasks[i]["radius"] or 0) >= 1],
        "no_finite_radius": [i for i in ids if tasks[i]["radius_status"] != "reached"],
        "pool_contains_edit": [i for i in ids if recall(pool(tasks[i]), tasks[i]["edited_files"], 99) > 0],
    }
    pos = {i: n for n, i in enumerate(ids)}
    summary["slices"] = {
        s: {"tasks": len(v), **{n: round(sum(per[n][1][pos[i]] for i in v) / len(v), 4) if v else None
                                for n in per}}
        for s, v in slices.items()
    }
    summary["slices_metric"] = "recall@1"
    (HERE / "results" / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
