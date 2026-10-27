"use client";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Search, SlidersHorizontal } from "lucide-react";
import { atlas } from "@/lib/atlas";
import { excerpt, filterTasks, formatNumber, formatRadius, type RadiusFilter } from "@/lib/helpers";
import type { Task } from "@/lib/types";
import { ReceiptDrawer } from "./receipt-drawer";

export function TaskBrowser() {
  const params = useSearchParams();
  const initialRepo = params.get('repo');
  const [repo,setRepo] = useState(initialRepo && atlas.repos.some(r=>r.repo===initialRepo)?initialRepo:'all');
  const [query,setQuery] = useState('');
  const [radius,setRadius] = useState<RadiusFilter>('all');
  const [page,setPage] = useState(0);
  const [selected,setSelected] = useState<Task|null>(null);
  const tasks = useMemo(()=>filterTasks(atlas.instances,query,repo,radius),[query,repo,radius]);
  const pageSize=15;
  const reset=()=>{setRepo('all');setQuery('');setRadius('all');setPage(0);};
  return <>
    <div className="section-heading"><div><p className="section-index">02 / THE TASK ARCHIVE</p><h2>Pick a clue. Follow it home.</h2></div><SlidersHorizontal size={22}/></div>
    <p className="section-description">Search the issues, narrow the distance, and open a task for its localization receipt.</p>
    <div className="filter-grid"><label className="search-field"><span>SEARCH THE ARCHIVE</span><div><Search size={16}/><input value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} placeholder="Issue, identifier, or file path…"/></div></label><label><span>REPOSITORY</span><select value={repo} onChange={e=>{setRepo(e.target.value);setPage(0);}}><option value="all">All repositories</option>{atlas.repos.map(r=><option key={r.repo} value={r.repo}>{r.repo}</option>)}</select></label><label><span>LOCALIZATION RADIUS</span><select value={radius} onChange={e=>{setRadius(e.target.value as RadiusFilter);setPage(0);}}><option value="all">Any distance</option><option value="0">0 hops · direct mention</option><option value="1">1 hop</option><option value="2">2 hops</option><option value="3+">3+ hops</option><option value="null">Unresolved · all</option><option value="no_mentions">No resolved mentions</option><option value="unreachable">Edit unreachable</option></select></label></div>
    <div className="results-status"><span role="status">{tasks.length} / {atlas.overall.instances} TASKS FOUND</span><button onClick={reset}>Reset filters ↺</button></div>
    {tasks.length ? <><div className="task-list" key={`${query}:${repo}:${radius}:${page}`}><div className="task-list-head" aria-hidden="true"><span>ISSUE / REPOSITORY</span><span>RADIUS</span><span>CONTEXT EST.</span><span/></div>{tasks.slice(page*pageSize,(page+1)*pageSize).map((task,i)=><button className="task-row" key={task.instance_id} style={{animationDelay:`${Math.min(i*25,250)}ms`}} onClick={()=>setSelected(task)} aria-label={`Open ${task.instance_id}, ${formatRadius(task.radius)}`}><span className="task-main"><span className="task-id">{task.instance_id}</span><strong>{excerpt(task.problem_statement,110)}</strong><small>{task.repo} · {task.edited_files.length} edited file{task.edited_files.length===1?'':'s'}</small></span><span className={`radius-chip ${task.radius===null?'unresolved':task.radius===0?'direct':''}`}>{task.radius===null?'—':task.radius}<small>{task.radius===null?'unresolved':'hops'}</small></span><span className="task-budget">{formatNumber(task.context_budget_tokens)}<small>tokens{task.radius_status==='unreachable'?' · exhausted':''}</small></span><ArrowRight size={17}/></button>)}</div><div className="pagination"><span>Page {page+1} of {Math.ceil(tasks.length/pageSize)}</span><div><button disabled={page===0} onClick={()=>setPage(p=>p-1)}>← Previous</button><button disabled={(page+1)*pageSize>=tasks.length} onClick={()=>setPage(p=>p+1)}>Next →</button></div></div></> : <div className="empty-state"><span aria-hidden="true">[ NO SIGNAL ]</span><h3>No tasks match these filters.</h3><p>Try a shorter query or a wider radius.</p><button onClick={reset}>Clear filters and start again</button></div>}
    <ReceiptDrawer task={selected} onClose={()=>setSelected(null)}/>
  </>;
}
