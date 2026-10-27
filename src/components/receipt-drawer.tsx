"use client";

import { useEffect, useRef } from "react";
import { ArrowDown, ArrowUpRight, Printer, X } from "lucide-react";
import type { Task } from "@/lib/types";
import { excerpt, formatNumber, formatRadius, formatPercent } from "@/lib/helpers";

/** Adapted from Qloo's native-dialog receipt pattern; focus returns to the opener. */
export function ReceiptDrawer({ task, onClose }: { task: Task | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (!task || !node) return;
    if (!node.open) node.showModal();
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = oldOverflow; node.close(); };
  }, [task]);

  return <dialog ref={dialog} className="receipt-drawer" aria-labelledby="receipt-title" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    {task && <div className="receipt-paper" key={task.instance_id}>
      <div className="drawer-top"><span><Printer size={16}/> LOCALIZATION RECEIPT</span><button type="button" aria-label="Close task details" onClick={onClose} autoFocus><X size={22}/></button></div>
      <p className="receipt-label">BUG COMPASS / ARCHIVE RECORD</p><h2 id="receipt-title">{task.instance_id}</h2>
      <div className="receipt-status"><strong>{formatRadius(task.radius)}</strong><span>{task.radius_status === 'reached' ? 'ROUTE FOUND' : task.radius_status === 'no_mentions' ? 'NO RESOLVED MENTIONS' : 'EDIT UNREACHABLE'}</span></div>
      <section className="receipt-section"><h3>01 / The issue</h3><blockquote>{excerpt(task.problem_statement)}</blockquote><a className="receipt-source" href={`https://github.com/${task.repo}/commit/${task.base_commit}`} target="_blank" rel="noreferrer">Inspect base commit {task.base_commit.slice(0,8)} <ArrowUpRight size={13}/></a></section>
      <section className="receipt-section"><h3>02 / Clues in the text</h3><p>{task.resolved_mentions} of {task.mention_count} unique mentions resolved to {task.mentioned_files.length} file{task.mentioned_files.length === 1 ? '' : 's'}.</p>
        <div className="mention-list">{task.mentions.length ? task.mentions.map(mention=><details key={mention.text}><summary><code>{mention.text}</code><span>{mention.files.length ? `${mention.files.length} file${mention.files.length===1?'':'s'}` : 'unresolved'}</span></summary>{mention.files.length ? mention.files.map(file=><code className="resolved-file" key={file}>{file}</code>) : <p>No Python file or indexed symbol matched at this commit.</p>}</details>) : <p className="empty-note">No eligible file paths, dotted references, or indexed code identifiers were found.</p>}</div>
      </section>
      <section className="receipt-section"><h3>03 / The shortest route</h3>{task.hop_path.length ? <ol className="hop-chain">{task.hop_path.map((file,i)=><li key={file}>{i>0 && <div className="chain-arrow"><ArrowDown size={16}/><span>import connection · either direction</span></div>}<div className="terminal-node"><span>{String(i).padStart(2,'0')} / {i===0?'ISSUE MENTION':i===task.hop_path.length-1?'EDITED FILE':'IMPORT NEIGHBOR'}{task.hop_path.length===1?' + EDITED FILE':''}</span><code>{file}</code></div></li>)}</ol> : <p className="empty-note">{task.radius_status==='no_mentions'?'There is no starting file for graph search. Try text retrieval to choose a seed.':'The mentioned files and edited files are disconnected in this static import graph.'}</p>}</section>
      <section className="receipt-section"><h3>04 / The context estimate</h3><div className="budget-total"><strong>{formatNumber(task.context_budget_tokens)}</strong><span>estimated tokens<br />characters ÷ 4</span></div><p>{task.visited_files} files visited · {formatNumber(task.repo_py_files)} Python files in the snapshot.</p><p className="receipt-small">{task.radius_status==='unreachable'?'This is the exhausted reachable component; no edit was reached.':'Includes files visited in deterministic breadth-first order through the first edited file.'} This is a retrospective estimate, not a model token count.</p></section>
      <section className="receipt-section"><h3>05 / Where the patch landed</h3>{task.edited_functions.map(change=><div className="edited-file" key={change.file}><code>{change.file}</code><p>{change.functions.length ? change.functions.join(', ') : 'No enclosing base-commit definition'}</p>{change.added_definitions.length>0 && <small>Added definition lines: {change.added_definitions.join(', ')}</small>}</div>)}</section>
      <section className="receipt-section"><h3>06 / Retrieval receipt</h3><div className="receipt-baselines">{(['bfs','bm25'] as const).map(b=><details key={b}><summary>{b==='bfs'?'BFS from mentions':'BM25 text search'}<span>R@10 {formatPercent(task.baselines[b]['recall@10'])}</span></summary><ol>{task.baselines[b].top_files.map(file=><li key={file}><code>{file}</code>{task.edited_files.includes(file) && <strong> [EDIT]</strong>}</li>)}</ol>{!task.baselines[b].top_files.length && <p>No ranked files.</p>}</details>)}</div></section>
      <p className="receipt-small">Static imports can miss dynamic loading, re-exports, and runtime behavior. Gold patch labels are used only for evaluation.</p>
      <div className="receipt-footer"><span className="barcode" aria-hidden="true"/><span>FOLLOW THE CLUE. FIND THE FIX.</span></div>
    </div>}
  </dialog>;
}
