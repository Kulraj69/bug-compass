import Link from "next/link";
import { ArrowRight, CornerDownRight } from "lucide-react";
import { atlas } from "@/lib/atlas";
import { formatNumber, formatPercent, histogram } from "@/lib/helpers";

export default function Overview() {
  const { overall } = atlas;
  const repoBins = new Map(atlas.repos.map(repo => [repo.repo, histogram(atlas.instances.filter(task => task.repo === repo.repo).map(task => task.radius))]));
  const max = Math.max(1, ...Array.from(repoBins.values()).flatMap(bins => bins.map(bin => bin.count)));
  return <>
    <div className="section-heading"><div><p className="section-index">01 / THE LAY OF THE CODE</p><h2>A map before the journey.</h2></div><span className="data-badge"><i/>MEASURED, NOT GENERATED</span></div>
    <p className="section-description">Real issues. Historical repositories. One question: how many imports away is the edited file?</p>
    <div className="stats-grid">
      {[{value:formatNumber(overall.instances),label:"BUGS ON THE MAP",note:"SWE-bench Lite test tasks"},{value:formatNumber(overall.repos),label:"REPOSITORIES",note:"Each at its original commit"},{value:formatNumber(overall.direct_instances),label:"ALREADY IN SIGHT",note:"An edited file is mentioned · 0 hops"},{value:formatNumber(overall.median_budget_tokens_reached),label:"MEDIAN CONTEXT ESTIMATE",note:"Chars ÷ 4 · reached tasks only"}].map((stat,i)=><div className="stat" key={stat.label}><span className="stat-number">{stat.value}<small>{String(i+1).padStart(2,"0")}</small></span><h3>{stat.label}</h3><p>{stat.note}</p></div>)}
    </div>
    <div className="insight-strip"><CornerDownRight size={20}/><p><strong>{overall.reached_instances} tasks have a route to an edit.</strong> {overall.no_mention_instances} have no resolved mentions; {overall.unreachable_instances} have mentions but no route.</p><Link href="/tasks">Explore tasks <ArrowRight size={15}/></Link></div>
    <section className="chart-section" aria-labelledby="histogram-title"><div className="subsection-heading"><div><p className="section-index">DISTANCE / BY REPOSITORY</p><h3 id="histogram-title">How far from a clue?</h3></div><div className="chart-legend"><span><i/>Import hops</span><span><i/>Unresolved</span></div></div>
      <p className="small-note">Tasks per radius. Bar height uses the same scale across repositories. “—” means no finite route was found.</p>
      <div className="histogram-grid">{atlas.repos.map(repo=>{
        const bins=repoBins.get(repo.repo)!;
        return <Link href={`/tasks?repo=${encodeURIComponent(repo.repo)}`} className="histogram-card" key={repo.repo} aria-label={`Browse ${repo.repo}: ${repo.instances} tasks`}>
          <div><h4>{repo.repo.split("/")[1]}</h4><span>{repo.instances} tasks</span></div>
          <svg viewBox="0 0 240 116" role="img" aria-label={`${repo.repo}: ${bins.map(bin=>`${bin.label === 'null' ? 'unresolved' : bin.label + ' hops'}: ${bin.count}`).join(', ')}`}>
            <path d="M10 90h220M10 53h220M10 16h220" stroke="currentColor" strokeOpacity=".12" strokeDasharray="2 4"/>
            {bins.map((bin,i)=>{const height=bin.count/max*68; return <g key={bin.label}><rect x={18+i*45} y={90-height} width="25" height={Math.max(bin.count ? 2 : 0,height)} rx="1" fill={bin.label==='null'?'#d4c3a0':'#bce5ce'}/><text x={30+i*45} y={Math.max(11,85-height)} textAnchor="middle" className="bar-value">{bin.count || ''}</text><text x={30+i*45} y="109" textAnchor="middle">{bin.label==='null'?'—':bin.label}</text></g>;})}
          </svg>
        </Link>;
      })}</div>
    </section>
    <section aria-labelledby="baseline-title" className="baseline-section"><div className="subsection-heading"><div><p className="section-index">RETRIEVAL / TWO WAYS IN</p><h3 id="baseline-title">Follow the graph. Or follow the words.</h3></div><Link className="text-link" href="/method">Read the method <ArrowRight size={14}/></Link></div>
      <p className="small-note">Recall@k: the fraction of edited files in the first k results, averaged equally over tasks. Higher is better.</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable recall comparison"><table className="recall-table"><caption className="visually-hidden">File recall for BFS and BM25, overall and by repository</caption><thead><tr><th rowSpan={2} scope="col">Repository</th><th colSpan={3} scope="colgroup">BFS from mentions</th><th colSpan={3} scope="colgroup">BM25 text search</th></tr><tr>{['BFS','BM25'].flatMap(b=>[1,5,10].map(k=><th scope="col" key={`${b}${k}`}>@{k}</th>))}</tr></thead><tbody>{[{...overall,repo:"Overall"},...atlas.repos].map(repo=><tr key={repo.repo} className={repo.repo==='Overall'?'overall-row':''}><th scope="row">{repo.repo==='Overall'?'All repositories':repo.repo}</th>{(['bfs','bm25'] as const).flatMap(b=>(['recall@1','recall@5','recall@10'] as const).map(k=><td key={`${b}${k}`}>{formatPercent(repo.baselines[b][k])}</td>))}</tr>)}</tbody></table></div>
    </section>
    <div className="screen-cta"><span>YOUR NEXT MOVE</span><p>Find an issue. Trace the path to its fix.</p><Link href="/tasks">Open task browser <ArrowRight size={17}/></Link></div>
  </>;
}
