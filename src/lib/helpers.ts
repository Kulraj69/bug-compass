import type { Task } from "./types";

export type RadiusFilter = "all" | "0" | "1" | "2" | "3+" | "null" | "no_mentions" | "unreachable";
export function filterTasks(tasks: Task[], query = "", repo = "all", radius: RadiusFilter = "all") {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return tasks.filter(task => {
    if (repo !== "all" && task.repo !== repo) return false;
    if (radius === "null" && task.radius !== null) return false;
    if ((radius === "no_mentions" || radius === "unreachable") && task.radius_status !== radius) return false;
    if (radius === "3+" && (task.radius === null || task.radius < 3)) return false;
    if (["0", "1", "2"].includes(radius) && task.radius !== Number(radius)) return false;
    const haystack = `${task.instance_id} ${task.repo} ${task.problem_statement} ${task.edited_files.join(" ")}`.toLowerCase();
    return terms.every(term => haystack.includes(term));
  });
}

export const BIN_LABELS = ["0", "1", "2", "3+", "null"] as const;
export function histogram(radii: (number | null)[]) {
  const bins: Record<(typeof BIN_LABELS)[number], number> = { "0": 0, "1": 0, "2": 0, "3+": 0, "null": 0 };
  radii.forEach(radius => { bins[radius === null ? "null" : radius >= 3 ? "3+" : String(radius) as "0" | "1" | "2"]++; });
  return BIN_LABELS.map(label => ({ label, count: bins[label] }));
}
export function formatNumber(value: number | null): string {
  return value === null ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}
export function formatPercent(value: number): string { return `${(value * 100).toFixed(1)}%`; }
export function formatRadius(value: number | null): string { return value === null ? "Unresolved" : `${value} ${value === 1 ? "hop" : "hops"}`; }
export function excerpt(value: string, limit = 300): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length <= limit ? normalized : `${normalized.slice(0, Math.max(0, limit - 1))}…`;
}
