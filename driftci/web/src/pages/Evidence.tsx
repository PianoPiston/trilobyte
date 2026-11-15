import {
  ArrowRight,
  Database,
  FileCode2,
  FileSearch,
  FilterX,
  Globe2,
  Link2,
  ReceiptText,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import type { Bootstrap, CodeEvidence, SourceReceipt, View } from '../types';
import { formatDate, modeKind, plural } from '../utils';
import {
  Button,
  CodeEvidence as RepositoryEvidence,
  EmptyState,
  ModeBadge,
  PageHeading,
  SeverityBadge,
  SourceReceiptCard,
} from '../components/ui';

interface EvidenceEntry {
  id: string;
  entityId: string;
  entityTitle: string;
  entityType: 'signal' | 'incident';
  severity?: string;
  receipt: SourceReceipt;
  files: CodeEvidence[];
  paths: string[];
}

export function Evidence({ data, onSelectSignal, onNavigate }: {
  data: Bootstrap;
  onSelectSignal: (id: string) => void;
  onNavigate: (view: View) => void;
}) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('');

  const entries = useMemo<EvidenceEntry[]>(() => {
    const records: EvidenceEntry[] = [];
    data.signals.forEach((signal) => {
      signal.source_receipts.forEach((receipt, index) => records.push({
        id: `${signal.id}:${index}`,
        entityId: signal.id,
        entityTitle: signal.title,
        entityType: 'signal',
        severity: signal.severity,
        receipt,
        files: signal.evidence,
        paths: [],
      }));
    });
    [...data.incidents, ...data.history].forEach((incident) => {
      incident.source_receipts.forEach((receipt, index) => records.push({
        id: `${incident.id}:${index}`,
        entityId: incident.id,
        entityTitle: `${incident.cve} · ${incident.title}`,
        entityType: 'incident',
        severity: incident.severity,
        receipt,
        files: incident.affected_files,
        paths: [],
      }));
    });
    return records.sort((a, b) => new Date(b.receipt.retrieved_at).getTime() - new Date(a.receipt.retrieved_at).getTime());
  }, [data]);

  const modes = useMemo(() => [...new Set(entries.map((entry) => modeKind(entry.receipt.mode)))], [entries]);
  const filtered = entries.filter((entry) => {
    if (mode && modeKind(entry.receipt.mode) !== mode) return false;
    const normalized = query.trim().toLowerCase();
    if (!normalized) return true;
    return [entry.receipt.publisher, entry.receipt.title, entry.receipt.quote, entry.receipt.url, entry.entityTitle]
      .some((value) => value.toLowerCase().includes(normalized));
  });

  return (
    <div className="page evidence-page">
      <PageHeading
        eyebrow="Evidence ledger"
        title="Every decision has a receipt."
        description="Publisher, retrieval context and affected code kept together for review."
        actions={<div className="evidence-principle"><Link2 aria-hidden="true" /><span>Source-to-code traceability</span></div>}
      />

      <section className="evidence-stats" aria-label="Evidence index metrics">
        <div><ReceiptText aria-hidden="true" /><strong>{data.metrics.source_receipts}</strong><span>Source receipts</span></div>
        <div><FileCode2 aria-hidden="true" /><strong>{data.metrics.files_indexed}</strong><span>Files indexed</span></div>
        <div><Database aria-hidden="true" /><strong>{data.metrics.dependencies_indexed}</strong><span>Dependencies indexed</span></div>
        <div><Globe2 aria-hidden="true" /><strong>{data.metrics.context_queries}</strong><span>Context.dev queries</span></div>
      </section>

      <section className="watched-source-section">
        <div className="section-heading"><div><h2>Watched sources</h2><p>Latest status reported by the workspace index.</p></div></div>
        {data.sources.length ? (
          <div className="watched-source-grid">
            {data.sources.map((source) => (
              <a href={source.url} target="_blank" rel="noreferrer noopener" className="watched-source" key={source.id}>
                <div><span className="source-publisher-mark"><ShieldCheck aria-hidden="true" /></span><ModeBadge mode={source.status} /></div>
                <strong>{source.publisher}</strong>
                <span>{source.title}</span>
                <small>Checked {formatDate(source.last_checked_at, true)} · {plural(source.event_count, 'event')}</small>
              </a>
            ))}
          </div>
        ) : <p className="muted-copy">No watched sources were returned by the API.</p>}
      </section>

      <section className="evidence-ledger-section">
        <div className="evidence-toolbar">
          <div>
            <h2>Source receipts</h2>
            <p>{plural(filtered.length, 'receipt link')} across web decisions and vulnerability incidents</p>
          </div>
          <label className="search-field">
            <span className="sr-only">Search evidence</span>
            <Search aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search publisher, source or decision" />
          </label>
        </div>
        <div className="mode-filters" aria-label="Filter evidence by retrieval mode">
          <button className={!mode ? 'active' : ''} aria-pressed={!mode} onClick={() => setMode('')}>All modes<span>{entries.length}</span></button>
          {modes.map((value) => (
            <button key={value} className={mode === value ? 'active' : ''} aria-pressed={mode === value} onClick={() => setMode(value)}>
              {value === 'replay' ? 'Historical replay' : value[0].toUpperCase() + value.slice(1)}
              <span>{entries.filter((entry) => modeKind(entry.receipt.mode) === value).length}</span>
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="panel"><EmptyState icon={entries.length ? FilterX : FileSearch} title={entries.length ? 'No receipts match these filters' : 'No source receipts returned'} description={entries.length ? 'Clear the search and mode filter to see the full evidence ledger.' : 'A source receipt is attached whenever a signal or incident cites retrieved evidence.'} action={entries.length ? <Button icon={FilterX} onClick={() => { setMode(''); setQuery(''); }}>Clear filters</Button> : undefined} /></div>
        ) : (
          <div className="evidence-ledger-list">
            {filtered.map((entry) => (
              <article className="evidence-ledger-row" key={entry.id}>
                <SourceReceiptCard receipt={entry.receipt} />
                <div className="evidence-relation">
                  <div className="relation-heading">
                    <span>{entry.entityType === 'signal' ? 'Change decision' : 'Vulnerability incident'}</span>
                    {entry.severity && <SeverityBadge severity={entry.severity} />}
                  </div>
                  <h3>{entry.entityTitle}</h3>
                  {entry.files.length > 0 && <RepositoryEvidence evidence={entry.files} />}
                  {entry.paths.length > 0 && (
                    <ul className="affected-path-list">
                      {entry.paths.map((path) => <li key={path}><FileCode2 aria-hidden="true" /><code>{path}</code></li>)}
                    </ul>
                  )}
                  {!entry.files.length && !entry.paths.length && <p className="muted-copy">No repository files are attached to this relationship.</p>}
                  {entry.entityType === 'signal' ? (
                    <Button variant="ghost" size="small" onClick={() => onSelectSignal(entry.entityId)}>Open decision<ArrowRight aria-hidden="true" /></Button>
                  ) : entry.entityType === 'incident' ? (
                    <Button variant="ghost" size="small" onClick={() => onNavigate('vulnerabilities')}>Open vulnerability response<ArrowRight aria-hidden="true" /></Button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
