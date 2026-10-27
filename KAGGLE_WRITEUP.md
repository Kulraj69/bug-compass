# Bug Compass: Telling a 4B Local Model Where to Look

**Subtitle:** A localization atlas for SWE-bench Lite, and a controlled test of whether its structural signals help Gemma 4 E4B pick the file to edit, on CPU only

*Draft for the Kaggle Gemma 4 Developer Agent Paper Track. Not submitted. All numbers come from `data/atlas.json` or `gemma/results/summary.json` in the repository.*

## Abstract

Small coding agents that run on a laptop cannot read a whole repository, so the first hard step is choosing which files to open. We release Bug Compass, an atlas of all 300 SWE-bench Lite test tasks across 12 Python repositories. For every task it records the issue's resolvable mentions, a static import graph at the base commit, the import distance from the issue's mentions to the edited files, an estimate of how much context a breadth-first search would read, and two retrieval baselines (BM25 and BFS from mentions). We then use the atlas as a testbed for Gemma 4 E4B (4-bit QAT GGUF, llama.cpp, 8 CPU threads, no GPU). Gemma 4 reranks a pool of about 17 candidate files built without gold information. With the issue text and candidate paths only, Gemma 4 puts an edited file first in **52.0%** of tasks (recall@1), against **16.0%** for BM25 and **30.0%** for a non-LLM rule that sorts by the issue's mentions. Adding Bug Compass's per-file notes to the prompt does not change recall@1 (**51.0%**; paired 95% bootstrap interval for the difference **−4.3 to +2.0 points**) and adds a small gain at recall@5 (**59.3%** against **56.3%**, interval **+0.3 to +5.7**). The candidate pool does most of the work: on the 195 tasks where it contains an edited file, plain Gemma 4 picks one first **80.0%** of the time. The mean cost is under **9 seconds** and under **900 prompt tokens** per task on CPU. Code, prompts, raw model outputs, and a Kaggle notebook are included.

## 1. Introduction

Repository-level repair benchmarks such as SWE-bench [1] ask an agent to change real code so that hidden tests pass. Before any repair, the agent has to localize: find the files and functions that need to change. Systems built around frontier models handle this with long contexts, many tool calls, or both [3, 4]. A small open model on consumer hardware has neither luxury. Gemma 4 E4B has a 128K-token context window [6], but filling it on a CPU is slow. The Bug Compass atlas's own breadth-first estimate puts the median context needed to reach an edited file at **135,852** estimated tokens (characters / 4) for tasks where a route exists.

This paper asks two questions:

1. **Resource:** how far, in static import hops, is the code an issue mentions from the code that was actually edited, and how much context does a naive search read on the way?
2. **Application:** if a cheap, deterministic tool supplies a short candidate list with structural notes, can a 4B-class local model choose the right file, and do the notes matter?

Our contributions:

- **Bug Compass atlas:** 300 tasks, 12 repositories, per-task mentions, import graphs, localization radius, BFS hop paths, context estimates, and BM25/BFS rankings, with a static explorer and a pipeline that rebuilds the atlas in **227.75 seconds** with 4 workers.
- **Gemma 4 reranking experiment:** a fixed prompt, a gold-free candidate pool, two prompt conditions (with and without Bug Compass notes), a non-LLM control that uses the same notes, and paired bootstrap intervals. All raw Gemma 4 responses are committed (600 scored, plus 88 duplicate calls described in Section 3.2).
- **A reproducible CPU recipe:** one llama.cpp release binary and one public Apache 2.0 GGUF file, with no GPU and no API key.

## 2. The Bug Compass atlas

**Source and scope.** We use the full SWE-bench Lite test split [2]: 300 tasks with no sampling and no dropped failures. Each repository is cloned once as a bare, blobless Git repository. Only the Python files at each task's `base_commit` are fetched. No dependencies are installed.

**Graph.** Python's `ast` module extracts internal imports, resolving relative imports and common source-root layouts, plus top-level functions, classes, and direct methods. Each file is a node and each internal import an undirected edge. Unparseable files remain nodes with no edges.

**Mentions.** From the issue text we extract file paths, dotted references, and backticked or traceback identifiers that match the symbol index. An ambiguous mention expands to every matching file, and the atlas records that expansion.

**Labels.** Edited files and enclosing functions come from the reference patch. The patch is used only for labels and scoring, never for retrieval, candidate pools, or prompts.

**Metrics.**
- *Localization radius:* the minimum number of import hops from any mentioned file to any edited file (0 means an edited file is mentioned directly).
- *Context estimate:* the characters / 4 read by a deterministic multi-source BFS before it first touches an edited file. Its stopping rule depends on the gold file, so it is a retrospective measurement, not an agent policy.
- *Recall@k:* |top-k ∩ edited| / |edited|, averaged over tasks.

**What the atlas shows.**

| Radius (hops) | 0 | 1 | 2 | 3 | 4 | none |
|---|---:|---:|---:|---:|---:|---:|
| Tasks | 154 | 49 | 33 | 7 | 1 | 56 |

Of the 300 tasks, 245 have at least one resolved mention and 244 have a route to an edited file. 55 tasks have no usable mention, and one has mentions but no route. Half of all tasks name an edited file directly, yet the baselines are weak:

| Ranker (atlas) | R@1 | R@5 | R@10 |
|---|---:|---:|---:|
| BFS from mentions | 11.7% | 23.3% | 33.0% |
| BM25 over paths + symbols [5] | 16.0% | 42.0% | 56.3% |

A short route does not give a good ordering. Among reached tasks the median radius is **0**, but the median BFS context estimate is **135,852** tokens and the mean is **517,252**. Common method names create dozens of seeds, and the edited file gets buried among them. Results also vary by repository. On xarray (5 tasks) BFS recall@10 is 80.0% against 40.0% for BM25. On scikit-learn (23 tasks) it is 34.8% against 78.3%. These gaps motivated the experiment: the signals are present, but a fixed ordering rule uses them poorly.

## 3. Gemma 4 experiment

### 3.1 Setup

**Model and runtime.** `google/gemma-4-E4B-it-qat-q4_0-gguf` (file `gemma-4-E4B_q4_0-it.gguf`, 5.15 GB, Apache 2.0) [6, 7], served by the llama.cpp release b11913 `llama-server` [8] with an 8,192-token context, 8 threads, one slot, and no GPU. The machine had 8 CPU cores and 15 GB of RAM. Decoding used temperature 0, at most 128 new tokens, and Gemma 4 thinking disabled (`enable_thinking: false`). With thinking on, the 128-token budget was used up before any answer appeared. We set this once, before the scored runs, and did not tune the prompt afterwards.

**Candidate pool.** For each task, the pool is the union of the atlas's BFS top-10 and BM25 top-10 files. Neither ranking uses gold edits. The mean pool size is **17.38** files (max 20). The pool contains at least one edited file in **195 of 300** tasks, and its recall over all edited files is **65.0%**. That is the ceiling for every reranker in this section.

**Task.** The prompt holds the repository name, the first 2,500 characters of the issue, the candidate paths in alphabetical order, and an instruction to return a JSON list of up to five candidate paths, most likely first. Output is parsed leniently: the first JSON list, or `.py` paths found by regex. Only exact pool members are kept, so a hallucinated path can never score.

**Conditions.**
- **Gemma 4 + plain:** paths only.
- **Gemma 4 + compass:** each path carries Bug Compass notes, for example ``(issue names `separability_matrix`; text-match rank 3)``, or `(reached via imports only)`. The notes come from resolved mentions (up to three per file) and BM25 rank. No gold information is used.
- **mentions-first (no LLM):** a deterministic control that uses exactly the same notes. Mentioned files come first, then files by BM25 rank, then alphabetical order. It tests whether Gemma adds anything beyond sorting by the notes.
- **BM25, BFS:** the atlas baselines, scored on the same tasks.

Intervals are paired percentile bootstraps over tasks (10,000 resamples, seed 0) on per-task recall differences.

### 3.2 Results (all 300 tasks)

| Ranker | R@1 | R@5 |
|---|---:|---:|
| BFS from mentions | 11.7% | 23.3% |
| BM25 | 16.0% | 42.0% |
| mentions-first (same notes, no LLM) | 30.0% | 50.7% |
| Gemma 4 E4B + plain | 52.0% | 56.3% |
| **Gemma 4 E4B + compass** | **51.0%** | **59.3%** |
| Pool ceiling | 65.0% | 65.0% |

| Paired difference | R@1, 95% CI (points) | R@5, 95% CI (points) |
|---|---|---|
| compass − BM25 | +29.0 to +40.7 | +12.3 to +22.7 |
| compass − mentions-first | +15.7 to +26.3 | +4.3 to +13.0 |
| compass − plain | −4.3 to +2.0 | +0.3 to +5.7 |
| plain − BM25 | +30.0 to +42.0 | +8.7 to +20.0 |
| plain − mentions-first | +16.3 to +27.7 | +1.0 to +10.3 |

**The notes did not help at rank 1.** We expected Bug Compass's notes to be the main source of Gemma 4's gain. They were not. At recall@1, plain and compass are one point apart and the interval spans zero. At recall@5 the notes add 3.0 points, and that interval only just excludes zero. Both Gemma 4 conditions beat the mentions-first rule by 16 to 28 points at recall@1, so the model is doing more than sorting by mentions. For our original hypothesis this is a negative result, and we report it as one: given a good pool, a 4B model reading the raw issue already recovers most of what the mention notes encode.

**Where the gain comes from (recall@1 by slice).**

| Slice | Tasks | BM25 | mentions-first | Gemma 4 + plain | Gemma 4 + compass |
|---|---:|---:|---:|---:|---:|
| Edited file mentioned (radius 0) | 154 | 18.2% | 51.3% | 71.4% | 70.8% |
| Reached via imports (radius ≥ 1) | 90 | 10.0% | 0.0% | 17.8% | 20.0% |
| No finite radius | 56 | 19.6% | 19.6% | 53.6% | 46.4% |
| Pool contains an edited file | 195 | 24.6% | 46.2% | 80.0% | 78.5% |

Gemma 4 gains most where fixed rules fail. When the edited file is reached only through imports, the mentions-first rule scores 0.0% by construction, while Gemma 4 scores 17.8% plain and 20.0% with notes. On the 56 tasks with no finite radius, the notes appear to hurt: 53.6% plain against 46.4% with notes. One possible reason, which we have not tested, is that a weak text-match note pulls the model away from a file the issue describes in words. These slices are small, so the differences between the two Gemma 4 conditions within a slice should be read as hints, not findings.

**Cost.** Gemma 4 + compass averaged **8.84 s** and **878.5 prompt tokens** per task (2,650.8 s for all 300). Gemma 4 + plain averaged **8.65 s** and **701.5 prompt tokens** (2,594.1 s in total). In 7 compass runs and 14 plain runs, no valid candidate path came back, and these score zero. The box was shared with other processes, and `llama-server` was killed twice for running out of memory and then restarted. Restarts should not change outputs at temperature 0, but the timings are noisy and should be read as rough figures. After the restarts we passed `--cache-ram 0` to stop the prompt cache from growing. The plain run was also interrupted and resumed, and for 88 tasks a leftover second runner sent the same request to the same server at the same time. We score the first response for each task and commit the other 88 in `gemma/results/plain_duplicate_calls.jsonl`. 87 of the 88 pairs returned the same ranking, so outputs are close to deterministic but not exactly so. Queueing during that overlap inflates some plain timings.

## 4. Related work

**Benchmarks.** SWE-bench [1] introduced repository-level issue resolution from real GitHub issues. SWE-bench Lite [2] is its 300-task test subset, which we cover completely.

**Localization pipelines.** Agentless [3] shows that a fixed, hierarchical localize-then-repair pipeline can compete with agent loops. Its first stage narrows a repository to files using the model plus a structure listing, which is the role our pool and reranker play here. SWE-agent [4] localizes through tool calls in an agent-computer interface, spending steps instead of prompt tokens.

**Graph-guided localization.** RepoGraph [9] builds a line-level graph of definitions and references and retrieves keyword-centred subgraphs as context. LocAgent [10] builds a heterogeneous graph of files, classes, and functions with import, call, and inheritance edges, and lets an LLM agent search it. Bug Compass is deliberately simpler: file-level imports only, no traversal by the model. Its contribution is measurement, namely the radius and context estimates, plus a gold-free candidate pool small enough for a 4B model to rank in under 900 prompt tokens.

**Lexical retrieval.** BM25 [5] remains a strong baseline for code search. Our atlas baseline indexes only paths and symbol names.

**Small open models.** Gemma 4 [6, 7] targets phones and laptops with its E2B and E4B models. We test only E4B, at 4-bit, on CPU.

## 5. Limitations

- **Ceiling and scope.** The pool misses every edited file in 105 tasks. Only file-level localization is evaluated: no function-level localization, no repair, and no test runs.
- **One model, one prompt.** Only Gemma 4 E4B at Q4_0 was run. The prompt was written once and not tuned, but it was also not compared against alternative prompts. Larger Gemma 4 sizes, other quantizations, and thinking mode are untested.
- **Contamination.** SWE-bench issues and fixes are public and predate Gemma 4's training cutoff, so some recall may come from memorization. The plain-versus-compass comparison holds this constant, but absolute numbers may overstate performance on unseen repositories.
- **Static graph.** Dynamic imports, re-exports, runtime dispatch, and non-Python code are invisible to the graph. Ambiguous mentions expand to all matches.
- **Skewed sample.** Django contributes 114 tasks and SymPy 77, and recall is task-weighted. Slice and repository results come from small groups.
- **Retrospective context estimates.** These stop at the gold file, so they describe a policy's cost after the fact and are not an observable stopping rule.

## 6. Reproducibility

Everything needed is in `github.com/Kulraj69/bug-compass`:

- `pipeline/` rebuilds `data/atlas.json` from the public SWE-bench Lite parquet. Its SHA-256 and the pipeline hash are recorded in the atlas.
- `gemma/rerank.py` builds the pool and prompt and works with any OpenAI-compatible endpoint. Runs resume from `gemma/results/<cond>.jsonl`, which stores every raw response, its token usage, and its wall time.
- `gemma/evaluate.py` recomputes every number in Section 3 and writes `gemma/results/summary.json`.
- `gemma/test_gemma.py` checks that no gold file appears in any prompt, along with the pool, notes, and parser. The repository's 29 tests pass.
- `gemma/bug-compass-gemma4.ipynb` (Kaggle notebook) scores the committed runs in under a minute on CPU. It can also download the same llama.cpp build and GGUF and re-run both conditions on a subset.

Server command used:

```
llama-server -m gemma-4-E4B_q4_0-it.gguf -c 8192 -t 8 --port 8088 --host 127.0.0.1 -np 1 --cache-ram 0
```

## 7. Conclusion

Half of SWE-bench Lite issues name the file that was fixed, yet text search and import-graph search both put it first less than 17% of the time. A 4-bit Gemma 4 E4B on a CPU closes much of that gap when a cheap tool hands it a short, gold-free candidate list: 52.0% recall@1 out of a 65.0% pool ceiling, in under nine seconds per task. The structural notes we expected to help did not change recall@1 and helped only slightly at recall@5. For small local agents, the lesson is to spend deterministic compute on building a good candidate list, spend the model on choosing from it, and test rather than assume that extra hints help a model that can already read the issue.

## References

[1] C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press, K. Narasimhan. *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR 2024. arXiv:2310.06770.
[2] SWE-bench Lite. https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite
[3] C. S. Xia, Y. Deng, S. Dunn, L. Zhang. *Agentless: Demystifying LLM-based Software Engineering Agents.* arXiv:2407.01489, 2024.
[4] J. Yang, C. E. Jimenez, A. Wettig, K. Lieret, S. Yao, K. Narasimhan, O. Press. *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* NeurIPS 2024. arXiv:2405.15793.
[5] S. Robertson, H. Zaragoza. *The Probabilistic Relevance Framework: BM25 and Beyond.* Foundations and Trends in Information Retrieval, 2009.
[6] Google DeepMind. *Gemma 4 Technical Report.* arXiv:2607.02770, 2026. Model card: https://ai.google.dev/gemma/docs/core/model_card_4
[7] Google. `gemma-4-E4B-it-qat-q4_0-gguf`. https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf
[8] ggml-org. llama.cpp, release b11913. https://github.com/ggml-org/llama.cpp
[9] S. Ouyang et al. *RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph.* arXiv:2410.14684, 2024.
[10] Z. Chen et al. *LocAgent: Graph-Guided LLM Agents for Code Localization.* arXiv:2503.09089.

## License

Code: MIT (see `LICENSE`; see the note on Apache 2.0 for winners). Atlas annotations: CC BY 4.0. SWE-bench Lite and the upstream repositories keep their own licenses. Gemma 4 weights: Apache 2.0.
