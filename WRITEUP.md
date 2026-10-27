# Bug Compass: a localization atlas for small coding agents

*Kaggle Writeup draft — Best New Resource / developer-agent paper track.*

## The problem

A coding agent can spend its context window looking for the relevant file
before it attempts a repair. Issue reports offer uneven clues: a traceback,
a module name, a method in backticks, or only a description of behavior.
Repository size alone does not tell an agent how useful those clues are.

Bug Compass turns this search problem into an inspectable resource. For each
SWE-bench Lite test task, it asks: **how many static import connections separate
something named in the issue from a file edited by the reference patch?**
It pairs that distance with a concrete search order, a context-size estimate,
and simple retrieval baselines. The accompanying explorer makes each result
auditable through a receipt of mentions, files, and graph hops.

This is a localization dataset and evaluation tool. It does not claim to
solve the issues or demonstrate improved model performance.

## Dataset construction

The release contains **300 tasks across 12 repositories**, using the complete
Lite test split without sampling or dropping failures. The full pipeline run
took **227.75 seconds with 4 worker processes** on the execution environment.
Those are recorded run measurements, not a guarantee for other machines.
[Source: `data/atlas.json`, `overall.instances`, `overall.repos`,
`run.elapsed_seconds`, `run.workers`.]

The pipeline downloads the public Hugging Face parquet, records its URL and
SHA-256, and groups tasks by repository. Each repository is cloned once as a
bare, blobless Git repository. Python files are enumerated at the task's
`base_commit`, with only the required blobs fetched in batches. There are no
full working-tree checkouts or benchmark dependency installations.

Python AST parsing extracts internal imports and a symbol index of top-level
functions, classes, and direct methods. Relative imports and standard package
imports are resolved, including common source-root layouts. Each file is a
graph node; an import adds an undirected connection for this experiment.
Unparseable files remain nodes but contribute no extracted imports or symbols.

Issue processing extracts file paths, dotted references, and identifiers in
backticks or traceback frames that match the symbol index. Repeated mention
text is deduplicated. Ambiguous mentions expand to every matching file; the
release preserves those expansions rather than silently selecting a match.

The gold patch supplies edited-file labels and function annotations. Changed
old-side lines are mapped to the narrowest enclosing AST definition. Hunk
contexts are retained, and added definition lines are reported separately.
The patch is not used to build either retrieval ranking.

The output includes per-task JSON and CSV, repository summaries, overall
summaries, and measurement provenance. Git/parquet caches are not part of the
release. The explorer reads the committed JSON directly and needs no API keys.

## What the metrics mean

**Localization radius** is the minimum number of undirected import hops from
any resolved issue file to any edited file. A direct match has radius zero.
A null radius means either no issue mention resolved or no edited file was
reachable. The separate `radius_status` field distinguishes these cases.

**Context estimate** sums file character counts divided by four in a
deterministic, multi-source breadth-first search, stopping after visiting the
first edited file. Seeds and neighbors use alphabetical path order. This
includes off-path files visited before the target, not just the shortest path.
For an unreachable target, it measures the exhausted reachable component;
with no seeds, it is null. Aggregate budget statistics exclude unreached tasks.

This stopping rule is retrospective and uses the gold target. It is useful
for analyzing a retrieval policy, but a deployed agent cannot observe that
stopping condition. Characters divided by four are an estimate, not a
Gemma tokenizer measurement, a KV-cache estimate, or a latency measurement.

**Recall@k** is the fraction of edited files in the first k retrieved files,
averaged equally over tasks. All edited files count in the denominator, while
retrieval candidates are base-commit Python files. This definition generalizes
to multi-file patches; it is not defined as an any-hit task success metric.

The baselines are:

- **BFS from mentions:** deterministic graph traversal from the issue-derived
  seed set. Disconnected files are not appended to pad the ranking.
- **BM25:** issue text against file-path tokens and top-level symbol names,
  including class methods. Camel case, underscores, and separators split into
  tokens; repeated query terms count once. Parameters and tie-breaking rules
  are recorded under `method.bm25` and `method.ties` in the atlas.

## Findings

The measured radius distribution is:

| Radius | Tasks |
| --- | ---: |
| Direct / 0 hops | 154 |
| 1 hop | 49 |
| 2 hops | 33 |
| 3 hops | 7 |
| 4 hops | 1 |
| No finite radius | 56 |

[Source: `data/atlas.json`, `overall.radius_histogram`.]

**245 tasks** have at least one resolved mention, and **244** have a route to
an edited file. **55** have no resolved mentions; **1** has mentions but an
unreachable edit. This makes the missing-clue case distinct from graph
disconnection instead of assigning both an arbitrary large distance.
[Source: `overall.resolved_instances`, `overall.reached_instances`,
`overall.no_mention_instances`, `overall.unreachable_instances`.]

The overall retrieval comparison is:

| Baseline | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: |
| BFS from mentions | 11.7% | 23.3% | 33.0% |
| BM25 | 16.0% | 42.0% | 56.3% |

[Source: `data/atlas.json`, `overall.baselines.bfs` and
`overall.baselines.bm25`; fractions converted to percentages and rounded to
one decimal place.]

Text retrieval outperforms this unweighted BFS policy overall. A useful clue
is not necessarily a useful ordering: resolving a common method name can
produce many seeds, and alphabetical traversal can postpone the actual edit.
A short graph route therefore does not imply high early recall.

The context estimates reinforce that distinction. Among reached tasks, the
median radius is **0**, yet the median context estimate is **135,852.375**
tokens and the mean is **517,251.6618852459** estimated tokens. These are
full-file traversal estimates, not measured model input lengths. Even a
directly mentioned target can come after many ambiguous seeds in the fixed
ordering. Large files and import hubs also affect the budget.
[Source: `overall.median_radius_reached`,
`overall.median_budget_tokens_reached`, `overall.mean_budget_tokens_reached`.]

Repository-level results are not uniform. For xarray, BFS recall@10 is
**80.0%**, compared with **40.0%** for BM25, across only **5 tasks**. For
scikit-learn, the corresponding figures are **34.8%** and **78.3%**, across
**23 tasks**. These are descriptive slices, not statistically established
rankings of retrieval methods.
[Source: `repos[repo="pydata/xarray"]` and
`repos[repo="scikit-learn/scikit-learn"]`, fields `instances` and
`baselines.*.recall@10`; percentages rounded to one decimal place.]

A concrete long route is `django__django-15851`, with radius **4** and a
context estimate of **3,477,093.25**. Its recorded path runs from
`tests/i18n/sampleproject/manage.py` through Django's management and
configuration modules, then the PostgreSQL backend, to
`django/db/backends/postgresql/client.py`. The issue's `./manage.py` resolves
to an existing sample-project file: a useful illustration of how path
ambiguity can shape the measurement.
[Source: `instances[instance_id="django__django-15851"]`, fields `radius`,
`context_budget_tokens`, `mentions`, and `hop_path`.]

## How a small local agent could use it

For a Gemma 4-class local coding agent, the resource offers a way to evaluate
context acquisition before spending inference on repair. It does not require
the agent to fit a whole repository into its prompt.

A practical planner could resolve issue clues, rank candidate files with
lexical evidence, and then expand their import neighborhoods under a fixed
context cap. Symbol names or compact file summaries could be inspected before
full file contents. If the issue supplies no usable seeds, lexical retrieval
can provide starting candidates instead of attempting an empty graph search.

Bug Compass supplies retrospective targets for evaluating such policies:
which files were missed, how many neighbors were traversed, and how much
full-file context accumulated before an edit was reached. Radius should be
used together with mention ambiguity, fan-out, and file size. It cannot serve
as a context-budget prediction on its own.

A future experiment should tune caps on separate training/development data,
freeze the policy, and compare held-out retrieval, actual tokenizer counts,
repair success, and resource consumption. The present release has not run a
Gemma model or tested a hybrid planner, so it makes no claims about their
accuracy, speed, memory requirements, or improvement over the baselines.

## Limitations

The graph describes static Python imports, not function calls or execution.
Dynamic imports, re-export chains, runtime dispatch, unusual package roots,
and non-Python code can be missed. Unsupported syntax depends on the Python
parser version. Tests and examples are included as ordinary Python files and
can introduce misleading paths or ambiguous symbol matches.

Expanding every ambiguous mention can make radius optimistic while making
BFS expensive. Undirected edges ignore dependency direction. Alphabetical
ordering is reproducible but not semantically informed. A shortest route to
one edited file also does not describe all the files a repair needs.

Patch insertion boundaries can map to the preceding base definition; new
files have no base-commit graph node. Reference edits are useful localization
labels, not proof of the only correct repair location. Budget estimates use
a gold-aware stopping point and full files, so they should not be read as
an agent's observable stopping rule or minimum necessary context.

The split is concentrated in a few repositories: Django contributes
**114 tasks** and SymPy **77**. Other projects have much smaller samples.
[Source: `repos[repo="django/django"].instances` and
`repos[repo="sympy/sympy"].instances`.] Overall recall is task-weighted,
not an equal average of repositories. No uncertainty intervals, broader
benchmark coverage, or model-repair results are claimed.

## Release and license

The pipeline and explorer code are MIT licensed, copyright Kulraj Singh,
2026. The original Bug Compass annotations and dataset compilation are
released under CC BY 4.0. See `LICENSE`, `data/LICENSE`, and
`THIRD_PARTY_NOTICES.md` for attribution and upstream rights.

The source is [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite),
from the SWE-bench authors. Its [upstream license](https://github.com/SWE-bench/SWE-bench/blob/main/LICENSE)
and original project/issue rights remain applicable; the derived release
license does not replace them. Full repository snapshots and gold patches
are not redistributed. The supplied visual references are not shipped.

The JSON contains all numbers cited here. Reproduction and verification
commands are in `README.md`; the explorer's Method page exposes the same
measurement rules. This document is a draft, not a submitted Kaggle entry.
