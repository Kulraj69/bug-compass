# Bug Compass

**Every fix starts with finding it.** An open atlas of issue-to-edit distances
in SWE-bench Lite, with a CPU-only Python pipeline and a dreamcore terminal
explorer. The committed dataset is real output, not a fixture or model guess.

## Start here — do X, see Y

| Do this | See this |
| --- | --- |
| `npm install --include=dev --cache pipeline/.cache/npm` then `npm run dev` | Open http://localhost:3000 for measured headline numbers, repository histograms, and BFS/BM25 recall |
| Open `/tasks`, search/filter, then select a task | A thermal receipt with an issue excerpt, resolved mentions, import-hop chain, edited files/functions, and context estimate |
| Open `/method` | Definitions, evaluation rules, and limits in plain language |
| Open [data/atlas.json](data/atlas.json) or [data/atlas.csv](data/atlas.csv) | Every task, per-repository aggregates, overall results, and provenance |
| Read [WRITEUP.md](WRITEUP.md) | Kaggle draft with findings cited to exact JSON fields |
| Run the commands below | Reproduce the corpus and verify the application |

Requires Node 20.19+ and Python 3.11+ (the recorded run used Python 3.13).
No API key, server secret, paid model, or GPU is needed. Network access is
needed only for installing packages and the first dataset/repository download.
The explorer uses static data imports; all three routes are prerendered.
`predev` and `prebuild` copy the committed JSON and CSV to `public/` for download.

## Reproduce the pipeline

Keep dependencies and every cache inside this directory:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --cache-dir pipeline/.cache/pip -r pipeline/requirements.txt
.venv/bin/python -m pipeline.run --workers 4
```

See `data/atlas.json` and `data/atlas.csv`. The recorded complete run took
227.75 seconds with four worker processes (see `run.elapsed_seconds` in JSON),
including the initial parquet download and bare clones. Time on another
machine depends on network, Git, CPU, and memory; this is not a performance
guarantee. The implementation uses stdlib plus PyArrow; pytest is for tests.
Use fewer workers on memory-constrained systems. Python dependencies are
installed in a local venv to honor this workspace's directory boundary.

The pipeline discovers the test parquet through the public Hugging Face
parquet API, uses the documented resolve URL if discovery fails, and caches
the validated file. Each source project gets one bare `--filter=blob:none`
clone. `git ls-tree` selects Python blobs at each base commit; missing Python
objects are fetched in batches and read through `git cat-file --batch` (the
batched equivalent of `git show`). No full checkouts or dependency installs of
the benchmark repositories occur. A process pool works by repository and
reuses parsed blobs across commits. Results are cached by input/code hash.

Run with `--refresh` to recompute annotations using the existing Git cache.
The command fails rather than publishing a partial dataset if any repository
fails. Re-running a completed build reuses matching result caches. That run's
recorded elapsed time describes the cached run, not the initial cold run.

For metric details and field types see [data/README.md](data/README.md).
Python syntax unsupported by the running interpreter is skipped during AST
extraction and counted; the file remains a node. The graph models static
imports, not calls. Query seeds and rankings do not use gold edits; radius,
recall, and the retrospective stopping point do.

## Verify

```bash
.venv/bin/python -m pytest -q
npm test
npm run typecheck
npm run lint
npm run build
```

Expected: the Python and Vitest suites pass; TypeScript, ESLint, and the
production build complete successfully. Python tests cover imports, mentions,
patches, radius/BFS, BM25, and artifact integrity. Vitest covers filters,
binning, formatting, and the static data contract.

Optional desktop/mobile browser verification, against a production build:

```bash
PLAYWRIGHT_BROWSERS_PATH=./pipeline/.cache/browsers npx playwright install chromium
npm run test:e2e
```

See the browser test summary; diagnostic screenshots are written under
`pipeline/.cache/`. These tests exercise repository links, search/filter/reset,
pagination, native-dialog focus and Escape behavior, issue excerpt bounds,
route rendering, downloads, reduced motion, and mobile overflow.

## For AI judges and maintainers

- `pipeline/core.py`: pure AST, mention, patch, graph, and ranking functions.
- `pipeline/run.py`: public data acquisition, bare Git processing, process pool,
  aggregation, provenance, JSON and CSV output. No generative model is called.
- `data/atlas.json`: canonical numbers; `data/atlas.csv`: machine-readable rows.
- `src/lib/helpers.ts`: UI filtering and presentation; `src/components/`:
  terminal shell, original SVG scenery, archive, and receipt drawer.
- `src/app/`: overview, task browser, and method routes in Next.js 16 / React 19
  / TypeScript / Tailwind v4. A system monospace stack avoids font network calls.
- `WRITEUP.md`: submission draft only. Nothing has been submitted or deployed.

The Qloo package versions, Vercel install command, TypeScript/ESLint/Vitest
configuration, night-scene SVG, hardware styles, and dialog pattern were used
as the requested starting point. Vitest was updated to a patched release after
npm audit flagged the older copied test tooling. The two provided reference
images remain local and are neither served nor committed. Scenery is SVG/CSS.
The app respects reduced motion and uses semantic controls and a native modal.

Code is [MIT](LICENSE), © 2026 Kulraj Singh. The derived atlas is
[CC BY 4.0](data/LICENSE), with SWE-bench and original-project attribution;
upstream rights are preserved. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
