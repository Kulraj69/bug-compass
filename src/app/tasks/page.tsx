import { Suspense } from "react";
import { TaskBrowser } from "@/components/task-browser";
export default function TasksPage() {
  return <Suspense fallback={<p className="section-description">Reading the task archive…</p>}><TaskBrowser/></Suspense>;
}
