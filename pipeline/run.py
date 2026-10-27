"""Run with: .venv/bin/python -m pipeline.run --workers 4

No checkouts, model calls, authentication, or issue-derived gold hints. All
downloads and intermediate artifacts live under pipeline/.cache.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import time
import tokenize as python_tokenize
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from .core import (ParsedFile, parse_source, build_index, extract_mentions,
                   parse_patch, radius_metrics, bm25_ranking, recall_at)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "pipeline" / ".cache"
API = "https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Lite/parquet"
FALLBACK = "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/resolve/main/data/test-00000-of-00001.parquet"


def git(repo: Path, *args: str, input: bytes | None = None, timeout=600) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], input=input, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed for {repo.name}: {result.stderr.decode(errors='replace')[-1200:]}")
    return result.stdout


def dataset():
    import pyarrow.parquet as pq
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "test.parquet"
    source_path = CACHE / "source.json"
    if not path.exists():
        url = FALLBACK
        try:
            with urllib.request.urlopen(API, timeout=60) as response:
                payload = json.load(response)
            url = payload["default"]["test"][0]
        except (OSError, KeyError, TypeError, IndexError):
            pass
        request = urllib.request.Request(url, headers={"User-Agent": "BugCompass/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(body)
        pq.read_table(temporary)  # Validate before caching.
        temporary.replace(path)
        source_path.write_text(json.dumps({"url": url, "downloaded_at": datetime.now(timezone.utc).isoformat()}))
    return pq.read_table(path).to_pylist(), {**json.loads(source_path.read_text()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def repository(name: str) -> Path:
    destination = CACHE / "repos" / (name.replace("/", "__") + ".git")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["git", "clone", "--bare", "--filter=blob:none", "https://github.com/" + name + ".git", str(destination)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        if result.returncode:
            raise RuntimeError(f"Clone failed: {name}: {result.stderr.decode(errors='replace')[-1000:]}")
    return destination


def tree(repo: Path, commit: str) -> dict[str, str]:
    try:
        raw = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    except RuntimeError:
        git(repo, "fetch", "--filter=blob:none", "origin", commit)
        raw = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    entries = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.split()
        if kind == b"blob" and mode != b"120000" and name.endswith(b".py"):
            entries[name.decode("utf-8", errors="replace")] = oid.decode()
    return entries


def read_blobs(repo: Path, oids: set[str]) -> dict[str, ParsedFile]:
    ordered = sorted(oids)
    # Avoid one network round trip per lazily fetched Python file. GitHub allows
    # explicit blob wants; only Python blobs required by these snapshots arrive.
    local_env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    checked = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname) %(objecttype)"],
                             input=("\n".join(ordered) + "\n").encode(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=local_env, check=True)
    missing = [line.split()[0].decode() for line in checked.stdout.splitlines() if line.endswith(b" missing")]
    for offset in range(0, len(missing), 2000):
        batch = missing[offset:offset + 2000]
        git(repo, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "--no-tags", "--no-write-fetch-head", "--stdin", "origin",
            input=("\n".join(batch) + "\n").encode(), timeout=900)
    raw = git(repo, "cat-file", "--batch", input=("\n".join(ordered) + "\n").encode(), timeout=900)
    stream = io.BytesIO(raw)
    parsed = {}
    for oid in ordered:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise RuntimeError(f"Missing Python blob {oid}")
        content = stream.read(int(header[2]))
        stream.read(1)
        try:
            encoding, _ = python_tokenize.detect_encoding(io.BytesIO(content).readline)
            source = content.decode(encoding)
        except (SyntaxError, UnicodeError, LookupError):
            parsed[oid] = ParsedFile([], [], [], len(content.decode(errors="replace")), False)
        else:
            parsed[oid] = parse_source(source)
    return parsed


def process_repo(name: str, tasks: list[dict], refresh: bool):
    result_path = CACHE / "results" / (name.replace("/", "__") + ".json")
    # Cached results are invalidated automatically when measurement code changes.
    fingerprint = hashlib.sha256((ROOT / "pipeline/core.py").read_bytes() + Path(__file__).read_bytes() + json.dumps(tasks, sort_keys=True).encode()).hexdigest()
    if result_path.exists() and not refresh:
        cached = json.loads(result_path.read_text())
        if cached["fingerprint"] == fingerprint:
            return cached["records"]
    started = time.monotonic()
    print(f"[{name}] cloning / indexing {len(tasks)} tasks", flush=True)
    repo = repository(name)
    trees = {commit: tree(repo, commit) for commit in sorted({t["base_commit"] for t in tasks})}
    all_oids = {oid for entries in trees.values() for oid in entries.values()}
    print(f"[{name}] reading {len(all_oids)} unique Python blobs", flush=True)
    blobs = read_blobs(repo, all_oids)
    records = []
    for task in tasks:
        files = {path: blobs[oid] for path, oid in trees[task["base_commit"]].items()}
        graph, symbols, modules = build_index(files)
        mentions = extract_mentions(task["problem_statement"], list(files), symbols, modules)
        seeds = sorted({p for mention in mentions for p in mention["files"]})
        # Rankings depend solely on repository contents and the issue text.
        bm25 = bm25_ranking(files, task["problem_statement"])
        changes = parse_patch(task["patch"], files)
        edited = sorted(c["file"] for c in changes)
        metrics, bfs = radius_metrics(graph, seeds, edited, {p: s.chars for p, s in files.items()})
        record = {
            "instance_id": task["instance_id"], "repo": name, "base_commit": task["base_commit"],
            "problem_statement": task["problem_statement"], "issue_excerpt": task["problem_statement"][:300],
            "mention_count": len(mentions), "resolved_mentions": sum(bool(m["files"]) for m in mentions),
            "mentions": mentions, "mentioned_files": seeds, "edited_files": edited, "edited_functions": changes,
            "repo_py_files": len(files), "unparsable_files": sum(not f.parsed for f in files.values()),
            "import_edges": sum(map(len, graph.values())) // 2, **metrics,
            "baselines": {"bfs": {"top_files": bfs[:10], **{f"recall@{k}": recall_at(bfs, edited, k) for k in (1, 5, 10)}},
                          "bm25": {"top_files": bm25, **{f"recall@{k}": recall_at(bm25, edited, k) for k in (1, 5, 10)}}},
        }
        records.append(record)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"fingerprint": fingerprint, "records": records}))
    print(f"[{name}] done in {time.monotonic() - started:.1f}s", flush=True)
    return records


def summarize(records):
    radii = [r["radius"] for r in records if r["radius"] is not None]
    budgets = [r["context_budget_tokens"] for r in records if r["radius"] is not None]
    count = len(records)
    return {
        "instances": count, "repos": len({r["repo"] for r in records}),
        "resolved_instances": sum(r["resolved_mentions"] > 0 for r in records),
        "reached_instances": len(radii), "no_mention_instances": sum(r["radius_status"] == "no_mentions" for r in records),
        "unreachable_instances": sum(r["radius_status"] == "unreachable" for r in records),
        "direct_instances": sum(r == 0 for r in radii),
        "radius_histogram": dict(sorted(Counter(str(r["radius"]) if r["radius"] is not None else "null" for r in records).items())),
        "median_radius_reached": median(radii) if radii else None,
        "median_budget_tokens_reached": median(budgets) if budgets else None,
        "mean_budget_tokens_reached": sum(budgets) / len(budgets) if budgets else None,
        "max_radius": max(radii) if radii else None,
        "baselines": {baseline: {f"recall@{k}": sum(r["baselines"][baseline][f"recall@{k}"] for r in records) / count if count else 0
                                  for k in (1, 5, 10)} for baseline in ("bfs", "bm25")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--refresh", action="store_true", help="Recompute results; retain downloaded Git objects")
    args = parser.parse_args()
    started = time.monotonic()
    tasks, source = dataset()
    groups = defaultdict(list)
    for task in tasks:
        groups[task["repo"]].append(task)
    records = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process_repo, repo, group, args.refresh) for repo, group in sorted(groups.items())]
        for future in as_completed(futures):
            records.extend(future.result())
    records.sort(key=lambda r: r["instance_id"])
    assert len(records) == len(tasks) and len({r["instance_id"] for r in records}) == len(tasks)
    atlas = {
        "schema_version": "1.0.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {"name": "princeton-nlp/SWE-bench_Lite", "split": "test", "license": "CC-BY-4.0", **source},
        "method": {"graph": "undirected static Python imports at base_commit", "tokens": "characters / 4; not model tokenization",
                   "recall": "macro mean of per-instance fraction of ALL edited files retrieved; Python-only candidates",
                   "ties": "lexicographic path order", "null_radius": "no resolved mention or edited file unreachable",
                   "budget": "BFS dequeue order through first edited file inclusive; all reachable files if unreachable; null if no seeds",
                   "mentions": "unique file/dotted candidates plus indexed identifiers in backticks and traceback frames; ambiguities expand to all matching files",
                   "source_parser": "Python ast; unsupported syntax is skipped, file remains a graph node",
                   "bm25": {"k1": 1.5, "b": 0.75, "query": "unique camel/snake/path-split issue tokens", "corpus": "file paths and top-level definitions/classes/methods"}},
        "run": {"elapsed_seconds": round(time.monotonic() - started, 2), "workers": args.workers,
                "python": __import__('platform').python_version(), "pipeline_sha256": hashlib.sha256((ROOT / 'pipeline/core.py').read_bytes() + Path(__file__).read_bytes()).hexdigest()},
        "overall": summarize(records),
        "repos": [{"repo": repo, **summarize([r for r in records if r["repo"] == repo])} for repo in sorted(groups)],
        "instances": records,
    }
    output = ROOT / "data"
    output.mkdir(exist_ok=True)
    (output / "atlas.json").write_text(json.dumps(atlas, indent=2, ensure_ascii=False) + "\n")
    columns = ["instance_id", "repo", "base_commit", "radius", "radius_status", "mention_count", "resolved_mentions", "mentioned_files", "edited_files", "edited_functions", "repo_py_files", "unparsable_files", "context_budget_tokens", "visited_files", "reachable_files", "seed_fan_out", "hop_path", "issue_excerpt"]
    baseline_columns = [f"{b}_recall@{k}" for b in ("bfs", "bm25") for k in (1, 5, 10)]
    with (output / "atlas.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns + baseline_columns)
        writer.writeheader()
        for record in records:
            row = {k: json.dumps(record[k]) if isinstance(record[k], (list, dict)) else record[k] for k in columns}
            row.update({f"{b}_recall@{k}": record["baselines"][b][f"recall@{k}"] for b in ("bfs", "bm25") for k in (1, 5, 10)})
            writer.writerow(row)
    print(json.dumps({"elapsed_seconds": atlas["run"]["elapsed_seconds"], "overall": atlas["overall"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
