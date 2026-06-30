import { candidates, docs, metrics, nav } from "@/lib/demo-data";

type SectionProps = { id: string; eyebrow: string; title: string; children: React.ReactNode };

function Section({ id, eyebrow, title, children }: SectionProps) {
  return (
    <section id={id} className="section-card">
      <div className="section-heading">
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Bar({ value }: { value: number }) {
  return <div className="bar"><i style={{ width: `${value}%` }} /></div>;
}

export function Dashboard() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">RP</div>
          <div>
            <strong>RecruitProof</strong>
            <small>CV Intelligence</small>
          </div>
        </div>
        <nav>
          {nav.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>
        <div className="sidebar-proof">
          <span>Proof mode</span>
          <strong>Synthetic 1M archive</strong>
          <small>Replace with Encore export after access approval.</small>
        </div>
      </aside>

      <div className="content">
        <header className="hero">
          <div>
            <p className="kicker">RECRUITPROOF · CV INTELLIGENCE</p>
            <h1>Your existing archive, unlocked.</h1>
            <p className="hero-copy">A private candidate intelligence layer that scans 500k-1M existing PDFs/DOCX files, finds rediscovery candidates, explains the match, and quantifies ATS replacement economics before asking for a migration.</p>
            <div className="hero-actions">
              <a href="#report">View Million-CV Proof</a>
              <a href="#storyboard" className="ghost">10-minute demo flow</a>
            </div>
          </div>
          <div className="hero-panel">
            <span>Warm search latency</span>
            <strong>4.2ms</strong>
            <small>FAISS candidate lookup on 1,024,871 synthetic profiles</small>
          </div>
        </header>

        <Section id="executive" eyebrow="First 30 seconds" title="Executive Dashboard">
          <div className="metric-grid">
            {metrics.map((m) => (
              <div className={`metric ${m.tone}`} key={m.label}>
                <span>{m.label}</span>
                <strong>{m.value}</strong>
                <small>{m.sub}</small>
              </div>
            ))}
          </div>
          <div className="candidate-list">
            {candidates.map((c) => (
              <article className="candidate" key={c.rank}>
                <div className="rank">#{c.rank}</div>
                <div className="candidate-main">
                  <div className="candidate-title"><strong>{c.name}</strong><span>{c.title}</span></div>
                  <Bar value={Number(c.score) * 10} />
                  <p>Missing: {c.missing}</p>
                  <small>→ {c.proof}</small>
                </div>
                <div className="score">{c.score}/10</div>
              </article>
            ))}
          </div>
        </Section>

        <Section id="import" eyebrow="Pipeline" title="Import Center: 500k-1M PDF/DOCX processing">
          <div className="split">
            <div className="pipeline-card"><h3>Ingestion status</h3><Bar value={87}/><p>892,341 PDFs parsed · 132,530 Word files parsed · 127 repair queue.</p></div>
            <div className="pipeline-card"><h3>Throughput</h3><strong>14,800 files/min</strong><p>Parallel extract → normalize → dedupe → embed → index.</p></div>
            <div className="pipeline-card"><h3>Failure handling</h3><strong>0.01%</strong><p>Corrupt PDFs, locked DOCX, image-only scans, malformed filenames.</p></div>
          </div>
        </Section>

        <Section id="intelligence" eyebrow="Archive intelligence" title="Hidden candidates, duplicates, stale records, skills, bottlenecks">
          <div className="insight-grid">
            {[
              ["Rediscovery", "3,842 high-fit candidates hidden outside recent searches"],
              ["Duplicates", "18,432 probable duplicates by email, phone, name, and semantic fingerprint"],
              ["Stale", "221,000 records older than 36 months need enrichment"],
              ["Skills", "Go, Kafka, Kubernetes, AWS, payments, platform engineering"],
              ["Bottleneck", "Resume text trapped in file attachments, not queryable fields"],
              ["Next action", "Run a role-specific audit against Encore export batch 001"],
            ].map(([a,b]) => <div className="insight" key={a}><span>{a}</span><strong>{b}</strong></div>)}
          </div>
        </Section>

        <Section id="search" eyebrow="Recruiter workflow" title="Enterprise Search Experience">
          <div className="search-box">Senior Backend Engineer · payments · Go · distributed systems · remote US</div>
          <div className="workflow"><span>Parse JD</span><span>Hybrid retrieval</span><span>Multi-signal rank</span><span>Explain fit</span><span>Export shortlist</span></div>
        </Section>

        <Section id="candidate" eyebrow="Candidate proof" title="Candidate Intelligence: why #1, missing skills, similar candidates, outreach">
          <div className="candidate-deep">
            <h3>Kwame O'Sullivan</h3>
            <p>{candidates[0].why}</p>
            <div className="chips">{candidates[0].matched.map((s) => <span key={s}>{s}</span>)}</div>
            <div className="outreach">Suggested outreach: “Kwame, we found your prior Vercel backend work in our archive and have a new payments infrastructure role that looks aligned with your distributed systems background.”</div>
          </div>
        </Section>

        <Section id="roi" eyebrow="Economics" title="Executive ROI Dashboard">
          <div className="roi-grid">
            <div><span>Current ATS Cost</span><strong>$171,000/year</strong></div>
            <div><span>RecruitProof Cost</span><strong>$24,000/year</strong></div>
            <div><span>Annual Savings</span><strong>$147,000 · 86%</strong></div>
            <div><span>Recruiter Hours Saved</span><strong>2,400/year</strong></div>
          </div>
          <div className="tco"><Bar value={86}/><p>5-year TCO delta: $735,000 estimated gross savings before implementation services.</p></div>
        </Section>

        <Section id="migration" eyebrow="Safe replacement" title="Migration Center: 6-phase dry run and rollback">
          <ol className="timeline">
            {['Read-only export', 'Parse and normalize', 'Dedupe and repair', 'Index and benchmark', 'Shadow recruiter workflow', 'Cutover or archive-only mode'].map((s, i) => <li key={s}><b>{i+1}</b><span>{s}</span><em>{i < 3 ? 'Complete' : 'Planned'}</em></li>)}
          </ol>
        </Section>

        <Section id="audit" eyebrow="Control plane" title="Audit Center: search history, recruiter actions, exports, security events">
          <div className="log-table">
            <div><b>09:14</b><span>Search: Senior Backend Engineer / Payments</span><em>Nick</em></div>
            <div><b>09:15</b><span>Shortlist exported: 25 candidates</span><em>PDF</em></div>
            <div><b>09:16</b><span>Security event: RBAC check passed</span><em>system</em></div>
          </div>
        </Section>

        <Section id="trust" eyebrow="Enterprise readiness" title="Trust Center: sovereignty, encryption, RBAC, PII, DR">
          <div className="trust-grid">
            {['Local-first deployment', 'Encryption at rest', 'Role-based access', 'PII minimization', 'Export controls', 'Disaster recovery'].map((x) => <div key={x}>✓ {x}</div>)}
          </div>
        </Section>

        <Section id="report" eyebrow="Killer artifact" title="Million-CV Proof Report: the 4 metrics Rudy needs">
          <div className="report-card">
            <strong>1,024,871 CVs scanned · 4.2ms warm search · 18,432 duplicates · $147,000 annual savings</strong>
            <p>This is the proof conversation: RecruitProof does not ask Rudy to rip out Encore first. It shows the archive value first, then earns the migration discussion.</p>
            <a href="/docs/proof/million_cv_scan/sample_report.md">Open sample report</a>
          </div>
        </Section>

        <Section id="storyboard" eyebrow="Meeting flow" title="Demo Storyboard: 10-minute close path">
          <div className="storyboard">
            {['This is not another sourcing tool', 'Here is your archive health', 'Here are candidates you already paid for', 'Here is the cost leakage', 'We can run read-only before replacement'].map((x, i) => <div key={x}><b>{i*2}-{i*2+2} min</b><span>{x}</span></div>)}
          </div>
        </Section>

        <Section id="docs" eyebrow="Viewable artifacts" title="Docs copied to /public/docs">
          <div className="doc-grid">
            {docs.map((d) => <a key={d} href={`/docs/${d}`}>{d}</a>)}
          </div>
        </Section>
      </div>
    </main>
  );
}
