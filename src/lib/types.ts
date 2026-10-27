export type Recall = { "recall@1": number; "recall@5": number; "recall@10": number };
export type Summary = {
  instances: number; repos: number; resolved_instances: number; reached_instances: number;
  no_mention_instances: number; unreachable_instances: number; direct_instances: number;
  radius_histogram: Record<string, number>; median_radius_reached: number | null;
  median_budget_tokens_reached: number | null; mean_budget_tokens_reached: number | null;
  max_radius: number | null; baselines: { bfs: Recall; bm25: Recall };
};
export type Task = {
  instance_id: string; repo: string; base_commit: string; problem_statement: string; issue_excerpt: string;
  mention_count: number; resolved_mentions: number; mentioned_files: string[];
  mentions: { text: string; kind: string; files: string[] }[];
  edited_files: string[];
  edited_functions: { file: string; functions: string[]; added_definitions: string[]; hunk_contexts: string[] }[];
  repo_py_files: number; unparsable_files: number; import_edges: number;
  radius: number | null; radius_status: string; hop_path: string[];
  context_budget_tokens: number | null; visited_files: number; reachable_files: number; seed_fan_out: number;
  baselines: { bfs: Recall & { top_files: string[] }; bm25: Recall & { top_files: string[] } };
};
export type Atlas = {
  schema_version: string; generated_at: string;
  dataset: { name: string; split: string; license: string; url: string; sha256: string; downloaded_at: string };
  run: { elapsed_seconds: number; workers: number; python: string; pipeline_sha256: string };
  overall: Summary; repos: (Summary & { repo: string })[]; instances: Task[];
};
