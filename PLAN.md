# Bug Compass — Kaggle Gemma 4 Developer Agent Paper Track (target: Best New Resource)

Deadline: Nov 12 11:59 PM UTC (Nov 13, 5:29 AM IST). Submission is a Kaggle Writeup (needs Kulraj's Kaggle account; do NOT submit).

## Idea
Small local coding agents fail first at *finding* the bug, not fixing it. Bug Compass is a dataset + tool that measures, for every SWE-bench Lite task, the "localization radius": how far (in repo import/call-graph hops) the edited code sits from anything the issue text names. It turns "this task is hard" into a number a 1-GPU agent can plan around (how much context to fetch, when to give up).

## Deliverables
1. Python pipeline `pipeline/` (no GPU, no paid API): loads SWE-bench Lite from the public HF datasets-server parquet, shallow-fetches each repo at base_commit, builds a file-level import graph + symbol index with `ast`, extracts symbols/paths named in the issue, parses gold patch for edited files/functions, computes radius (min hops), fan-out, and a "context budget" (tokens needed to reach the edit by BFS).
2. Baseline: BFS-from-issue-mentions file retrieval; report recall@k vs. BM25 over file paths. Pure CPU.
3. `data/atlas.json` (+ CSV) released under CC-BY-4.0.
4. Next.js dreamcore explorer (copied UI language from /workspace/devpost/qloo): radius histogram per repo, per-task drill-down showing the hop path from issue mention to edited file.
5. `WRITEUP.md` draft (<3,000 words) for the Kaggle Writeup, numbers taken only from the generated data.
6. Tests: vitest for app lib; pytest for graph/radius functions. MIT LICENSE for code.

## Odds (estimate)
Resource prize is judged on usefulness to the community; few entries will ship a reusable dataset + explorer. Estimated 0.5–1.5% overall.
