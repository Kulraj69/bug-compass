# Bug Compass atlas

`atlas.json` is the canonical release. `atlas.csv` is one row per task; arrays
and objects in CSV cells are JSON encoded. A blank CSV numeric cell is null,
not zero. CSV issue excerpts are untrusted text; import columns as text when
opening them in spreadsheet software.

Source: [SWE-bench Lite, test split](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite).
The JSON includes the exact parquet URL, SHA-256, download and generation
timestamps, measurement-code hash, Python version, worker count, and run time.
`dataset.license` denotes the Bug Compass derived release license, CC BY 4.0;
it does not assert a license for every upstream contribution. See [LICENSE](LICENSE).

## Schema (1.0.0)

| Field | Meaning |
| --- | --- |
| `instance_id`, `repo`, `base_commit` | Original benchmark identifiers and historical snapshot |
| `problem_statement`, `issue_excerpt` | Original issue text; excerpt is at most 300 characters |
| `mentions` | Unique candidate text, kind, and all matching Python file paths |
| `mention_count` | Number of unique candidate mentions, including unresolved file/dotted candidates |
| `resolved_mentions` | Number of candidates with at least one file match; **not** number of matching files |
| `mentioned_files` | Sorted union of all resolved mention files (BFS seeds) |
| `edited_files` | All files edited by the gold patch |
| `edited_functions` | Per-file base-commit symbol labels, added definition lines, and raw hunk contexts |
| `repo_py_files`, `unparsable_files` | Python files in the snapshot and files skipped by the AST parser |
| `import_edges` | Number of unique undirected edges |
| `radius` | Minimum import hops from any seed to any edited file; nullable |
| `radius_status` | `reached`, `no_mentions`, or `unreachable` |
| `hop_path` | Shortest route, inclusive of seed and edited file; empty for null radius |
| `context_budget_tokens` | Sum of visited file characters / 4, through first edit inclusive |
| `visited_files` | Number dequeued through first edit, or entire component if exhausted |
| `reachable_files` | All files reachable from the seeds |
| `seed_fan_out` | Distinct immediate neighbors of the seed set, excluding seeds |
| `baselines` | Top ten file paths and recall@1/5/10 for BFS and BM25 |
| `repos`, `overall` | Per-repository and task-weighted overall aggregates |

Null radius has two meanings, separated by `radius_status`. With no seeds the
budget is null. With seeds but no reachable edit it is the cost of exhausting
the reachable component. Summary budget statistics use **only reached tasks**.
Budgets use character counts, not bytes or a model tokenizer. Seed and
neighbor order is alphabetical; ambiguous names may resolve to many files.
A radius of zero can still require reading many files in this order.

Recall is the fraction of **all edited files** present in a baseline's first k
results, averaged equally across instances. Only base-commit Python files can
be retrieved. BFS does not pad disconnected components with arbitrary files.
BM25 returns lexical path order for ties, including zero-score ties. Neither
baseline receives gold edits as a ranking input. The stopping point used to
measure the context estimate does use gold edits, retrospectively.

Classes, top-level functions, and direct class methods are indexed. AST
ranges select the narrowest enclosing base-commit definition. Added-only
lines anchor to the preceding old line; completely new definitions are also
reported separately. Boundary insertions can be approximate. No source files
or full gold patches are included in this release.

Generate: `.venv/bin/python -m pipeline.run --workers 4` from the project root.
The Git/parquet cache is intentionally excluded from the release. Measurement
code changes invalidate result caches. Use `--refresh` to recompute even when
the code and inputs are unchanged.
