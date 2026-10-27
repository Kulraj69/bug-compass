"""Gemma 4 file-localization reranker on Bug Compass candidate pools.

For each SWE-bench Lite task in data/atlas.json, the candidate pool is the union
of the BFS and BM25 top-10 files (neither uses gold edits). Gemma 4 sees the
issue text and the pool, and returns the 5 files it would edit, ranked.

Conditions:
  plain   - issue + candidate paths (alphabetical)
  compass - same, plus Bug Compass signals per candidate: which issue mentions
            resolve to it, and its BM25 rank. No gold information.

Runs against any OpenAI-compatible endpoint (default: local llama.cpp server
with google/gemma-4-E4B-it-qat-q4_0-gguf). Results append to results/<cond>.jsonl
so the run can resume.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUE_CHARS = 2500


def pool(task: dict) -> list[str]:
    b = task["baselines"]
    return sorted(set(b["bfs"]["top_files"]) | set(b["bm25"]["top_files"]))


def annotations(task: dict) -> dict[str, str]:
    notes: dict[str, list[str]] = {}
    for m in task["mentions"]:
        for f in m["files"]:
            notes.setdefault(f, []).append(f"issue names `{m['text']}`")
    bm25 = task["baselines"]["bm25"]["top_files"]
    out = {}
    for f in pool(task):
        parts = list(dict.fromkeys(notes.get(f, [])))[:3]
        if f in bm25:
            parts.append(f"text-match rank {bm25.index(f) + 1}")
        out[f] = "; ".join(parts) if parts else "reached via imports only"
    return out


def build_prompt(task: dict, cond: str) -> str:
    issue = task["problem_statement"][:ISSUE_CHARS]
    files = pool(task)
    if cond == "compass":
        ann = annotations(task)
        listing = "\n".join(f"- {f}  ({ann[f]})" for f in files)
    else:
        listing = "\n".join(f"- {f}" for f in files)
    return (
        f"You are localizing a bug in the Python repository {task['repo']}.\n\n"
        f"ISSUE:\n{issue}\n\n"
        f"CANDIDATE FILES:\n{listing}\n\n"
        "Which candidate files must be edited to fix this issue? Reply with only a JSON "
        'list of up to 5 file paths copied exactly from the candidates, most likely first. '
        'Example: ["a/b.py", "a/c.py"]'
    )


def parse(text: str, files: list[str]) -> list[str]:
    found = []
    m = re.search(r"\[.*?\]", text, re.S)
    if m:
        try:
            found = [x for x in json.loads(m.group(0)) if isinstance(x, str)]
        except json.JSONDecodeError:
            found = []
    if not found:
        found = re.findall(r"[\w./-]+\.py", text)
    ranked = []
    for f in found:
        f = f.strip()
        if f in files and f not in ranked:
            ranked.append(f)
    return ranked[:5]


def call(base: str, model: str, prompt: str) -> tuple[str, dict]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 128,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(f"{base}/chat/completions", body, {"Content-Type": "application/json"})
    key = os.environ.get("GEMMA_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    return d["choices"][0]["message"]["content"] or "", d.get("usage", {})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", choices=["plain", "compass"], required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8088/v1")
    ap.add_argument("--model", default="gemma-4-E4B-it-qat-q4_0")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    tasks = json.load(open(ROOT / "data/atlas.json"))["instances"]
    if a.limit:
        tasks = tasks[: a.limit]
    out = Path(__file__).parent / "results" / f"{a.cond}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(l)["instance_id"] for l in out.open()} if out.exists() else set()
    with out.open("a") as fh:
        for t in tasks:
            if t["instance_id"] in done:
                continue
            files = pool(t)
            t0 = time.time()
            text, usage = call(a.base, a.model, build_prompt(t, a.cond))
            fh.write(json.dumps({
                "instance_id": t["instance_id"], "cond": a.cond, "model": a.model,
                "ranking": parse(text, files), "raw": text, "usage": usage,
                "seconds": round(time.time() - t0, 2),
            }) + "\n")
            fh.flush()


if __name__ == "__main__":
    main()
