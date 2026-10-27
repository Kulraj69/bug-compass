"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowDownToLine, ArrowUpRight } from "lucide-react";
import { NightScene } from "./night-scene";
import { CompassMark } from "./compass-mark";

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return <>
    <NightScene />
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="site-header"><div className="header-inner">
      <Link href="/" className="brand"><CompassMark /><span>bug compass<span className="brand-dot">✧</span></span></Link>
      <div className="header-note">A FIELD GUIDE TO FINDING THE FIX</div>
      <a className="download-link" href="/atlas.csv" download><ArrowDownToLine size={15} /><span>Get the dataset</span></a>
    </div></header>
    <div className="page-shell">
      <section className="hero"><div><p className="eyebrow"><span className="tiny-star">✧</span> LOCAL AGENTS · DISTANT BUGS</p>
        <h1>Every fix starts<br />with <em>finding it.</em><span className="terminal-cursor">_</span></h1>
        <p className="hero-description">How far is the fix from what the issue tells you?<br className="desktop-break" /> Follow the imports. Measure the distance. Plan your context.</p></div>
        <div className="hero-stamp"><span>RESEARCH STATION / 001</span><CompassMark /><strong>THE LOCALIZATION ATLAS</strong><small>SWE-bench Lite · test split<br />Open data. No model required.</small></div>
      </section>
      <main id="main-content" className="computer-case">
        <div className="workspace-topline"><span className="hardware-nameplate">BUG COMPASS <strong>5150</strong></span><span className="hardware-vents" aria-hidden="true"/><span className="power-label"><i/>DATA LOADED</span></div>
        <div className="crt-screen">
          <div className="screen-topline"><span>BC-DOS v1.0 / LOCALIZATION EXPLORER</span><span>READ-ONLY ARCHIVE</span></div>
          <nav className="terminal-tabs" aria-label="Explorer sections">{[{href:"/",label:"Overview",key:"01"},{href:"/tasks",label:"Task browser",key:"02"},{href:"/method",label:"Method",key:"03"}].map(tab => <Link key={tab.href} href={tab.href} aria-current={pathname === tab.href ? "page" : undefined}><span>{tab.key}</span>{tab.label}</Link>)}<span className="tab-prompt" aria-hidden="true">READY<span>▮</span></span></nav>
          <div className="screen-content">{children}</div>
          <div className="screen-bottom"><span>END OF BUFFER</span><span>SMALL MODELS. A LITTLE MORE DIRECTION.</span><span aria-hidden="true">■</span></div>
        </div>
        <div className="hardware-bottom"><span className="hardware-vents" aria-hidden="true"/><span>PERSONAL RESEARCH COMPUTER</span><span className="hardware-switch" aria-hidden="true">I / O</span></div>
      </main>
      <footer className="site-footer"><span>Built for the curious. And their local agents.</span><div><a href="/atlas.json" download>JSON <ArrowUpRight size={12}/></a><a href="/atlas.csv" download>CSV <ArrowUpRight size={12}/></a><span>DATA CC BY 4.0 · CODE MIT</span></div></footer>
    </div>
  </>;
}
