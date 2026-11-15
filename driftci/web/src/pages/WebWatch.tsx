import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Diff,
  Globe2,
  Link2,
  Plus,
  Radio,
  Search,
  Trash2,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { Bootstrap, Health } from '../types';
import { cx, domain, errorText, formatDate, label as labelMode, plural, relativeTime } from '../utils';
import {
  Button,
  EmptyState,
  IconButton,
  InlineNotice,
  ModeBadge,
  PageHeading,
  SectionHeading,
} from '../components/ui';

export function WebWatch({ data, health, busy, onAddWatch, onRemoveWatch, onSelectSignal }: {
  data: Bootstrap;
  health: Health | null;
  busy: string;
  onAddWatch: (url: string, title: string) => Promise<void>;
  onRemoveWatch: (key: string) => Promise<void>;
  onSelectSignal: (id: string) => void;
}) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [removing, setRemoving] = useState('');
  const sources = data.sources.filter((source) => source.watch || (source.category && source.category !== 'release_events'));
  const usage = health?.context_dev.usage;
  const credits = usage?.daily_credits ?? 0;
  const monitorCommitment = usage?.monitor_spent_and_reserved ?? 0;
  const reserved = usage?.ordinary_reserved_credits ?? 0;
  const committed = credits + monitorCommitment + reserved;
  const researchError = data.sources.find((source) => source.id === 'src-context-search')?.error;
  const limit = usage?.daily_credit_limit ?? 10_000;
  const cacheHours = Math.round((usage?.cache_ttl_seconds ?? 21600) / 3600);
  const monitor = data.monitor ?? health?.monitor;
  const monitorActive = monitor?.mode === 'remote_scheduled' && monitor.status === 'active';
  const run = monitor?.last_run;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      new URL(url);
      await onAddWatch(url.trim(), title.trim());
      setUrl('');
      setTitle('');
    } catch (requestError) {
      setError(requestError instanceof TypeError ? 'Enter a complete public HTTPS URL.' : errorText(requestError));
    }
  };

  const remove = async (key: string) => {
    setRemoving(key);
    setError('');
    try {
      await onRemoveWatch(key);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setRemoving('');
    }
  };

  return (
    <div className="page watch-page">
      <PageHeading
        eyebrow="Live web watch"
        title="Know when the source changes."
        description="Context.dev turns official docs, releases and pricing pages into comparable snapshots. DriftCI maps each observed change back to your repository."
      />

      <section className="context-hero">
        <div className="context-hero-main">
          <span className="context-logo"><Globe2 aria-hidden="true" /></span>
          <div>
            <span className="context-eyebrow"><Radio aria-hidden="true" />Context.dev web intelligence</span>
            <h2>{plural(sources.length, 'source')} under watch.</h2>
            <p>Local page checks use a {cacheHours}-hour shared cache. Any hosted Context.dev monitor has its own schedule and credit accounting below.</p>
          </div>
        </div>
        <div className="context-budget">
          <span>Local credits committed today</span>
          <strong>{committed}<small> / {limit} credits</small></strong>
          <div className="budget-track" aria-label={`${committed} of ${limit} daily Context.dev credits spent or reserved`}><span style={{ width: `${Math.min(100, committed / limit * 100)}%` }} /></div>
          <p>{credits} scrape/search spent · {monitorCommitment} monitor spent/reserved{reserved ? ` · ${reserved} in flight` : ''} · {usage?.daily_available ?? 0} available</p>
          {committed > limit && <p>Existing commitments exceed the daily ceiling. The active monitor is retained; additional ordinary requests and new schedules are blocked.</p>}
        </div>
      </section>

      {monitor && (
        <section className={`panel hosted-monitor ${monitorActive ? 'is-live' : ''}`} data-testid="hosted-monitor">
          <div className="hosted-monitor-heading">
            <div><span className="context-eyebrow"><Radio aria-hidden="true" />Context.dev remote scheduler</span><h2>{monitor.name ?? 'Repository security monitor'}</h2></div>
            <span className={`badge ${monitorActive ? 'mode-live' : 'mode-replay'}`}><span className={monitorActive ? 'live-dot' : ''} />{labelMode(monitor.status ?? monitor.mode)}</span>
          </div>
          {monitor.error && <InlineNotice tone="warning" role="status">{monitor.error} Existing evidence is retained; this attempt did not produce a live completion.</InlineNotice>}
          {monitor.target?.query && <div className="monitor-query"><span>Search query</span><code>{monitor.target.query}</code></div>}
          <dl className="monitor-facts">
            <div><dt>Schedule</dt><dd>{monitor.schedule === 'hourly' ? 'Every hour, run by Context.dev' : labelMode(monitor.schedule ?? 'unconfirmed')}</dd></div>
            <div><dt>Next remote run</dt><dd>{monitor.next_run_at ? formatDate(monitor.next_run_at, true) : 'Not supplied'}</dd></div>
            <div><dt>Monitor credits</dt><dd>{monitor.budget ? `${monitor.budget.spent} spent · ${monitor.budget.reserved} reserved` : 'Accounting unavailable'}</dd></div>
            <div><dt>Reconciled by this app</dt><dd>{monitor.last_polled_at ? relativeTime(monitor.last_polled_at) : 'Not yet reconciled'}</dd></div>
          </dl>
          {run ? (
            <div className="monitor-run">
              <div><span>{labelMode(run.run_type ?? 'run')} · {run.id}</span><strong>{run.status === 'completed' ? 'Completed remotely' : labelMode(run.status ?? 'unknown')}</strong></div>
              <p>{run.baseline_created ? 'Baseline stored. No change alert is created for a baseline.' : run.change_detected ? 'A new source change was observed and is available for repository review.' : 'The remote run completed without a change; no advisory or patch was created.'}</p>
              <small>{run.completed_at ? formatDate(run.completed_at, true) : run.started_at ? `Started ${formatDate(run.started_at, true)}` : 'Run timing unavailable'}{run.credits_charged !== undefined ? ` · ${run.credits_charged} credits` : ''}{run.skip_reason ? ` · ${run.skip_reason}` : ''}{run.error ? ` · ${run.error}` : ''}</small>
            </div>
          ) : <p className="monitor-pending">No completed remote run has been reconciled yet. The schedule status alone is not presented as live completion.</p>}
          <div className="monitor-footer"><code title={monitor.id}>{monitor.id}</code><span>Separate from the app’s 15-minute local polling. Webhook ingestion is not implemented.</span></div>
        </section>
      )}

      <section className="add-watch-bar">
        <div className="add-watch-intro"><Plus aria-hidden="true" /><div><strong>Watch a public web page</strong><span>Add a status page, policy, changelog or any operational source.</span></div></div>
        <form onSubmit={(event) => void submit(event)} noValidate>
          <label className="watch-title-input"><span className="sr-only">Watch name</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Name (optional)" maxLength={80} /></label>
          <label className="watch-url-input"><Link2 aria-hidden="true" /><span className="sr-only">Public HTTPS URL</span><input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://provider.com/changelog" /></label>
          <Button type="submit" variant="primary" icon={Plus} loading={busy === 'add-watch'}>Add watch</Button>
        </form>
      </section>
      {error && <InlineNotice tone="error" role="alert" className="watch-error">{error}</InlineNotice>}

      <div className="watch-overview-grid">
        <section className="panel observation-panel">
          <SectionHeading
            title="Observed changes"
            description="Only a changed snapshot creates an observation."
            action={<span className="count-label">{plural(data.changes.length, 'change')}</span>}
          />
          {data.changes.length ? (
            <div className="observation-list">
              {data.changes.slice(0, 10).map((change) => (
                <article className="observation-card" key={change.id}>
                  <div className="observation-marker"><Diff aria-hidden="true" /></div>
                  <div className="observation-content">
                    <div className="observation-meta"><span>{change.publisher}</span><time dateTime={change.observed_at}>{relativeTime(change.observed_at)}</time><ModeBadge mode={change.mode} /></div>
                    <a href={change.url} target="_blank" rel="noreferrer noopener"><strong>{change.title}</strong><ArrowUpRight aria-hidden="true" /></a>
                    <div className="change-counts"><span className="addition">+{change.added_lines} added</span><span className="deletion">−{change.removed_lines} removed</span>{change.matched_terms?.map((term) => <code key={term}>{term}</code>)}</div>
                    <div className="web-diff-preview">
                      {change.removed.slice(0, 2).map((line, index) => <div className="web-diff-line removed" key={`r${index}`}><span>−</span><code>{line}</code></div>)}
                      {change.added.slice(0, 3).map((line, index) => <div className="web-diff-line added" key={`a${index}`}><span>+</span><code>{line}</code></div>)}
                    </div>
                    {change.signal_id && <Button variant="ghost" size="small" onClick={() => onSelectSignal(change.signal_id!)}>Review repository impact<ArrowRight aria-hidden="true" /></Button>}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon={CheckCircle2} title="Baselines, not false alarms" description="The first successful retrieval establishes a snapshot. When a later retrieval differs, the exact added and removed lines appear here with repository evidence." />
          )}
        </section>

        <section className="panel watchlist-panel">
          <SectionHeading title="Watchlist" description="Repository-derived official pages and custom HTTPS watches." />
          {sources.length ? (
            <div className="watch-source-list">
              {sources.map((source) => (
                <article className={cx('watch-source-row', source.custom && 'custom-watch')} key={source.id}>
                  <a href={source.url} target="_blank" rel="noreferrer noopener" className="watch-source-link">
                    <span className="watch-source-icon"><Globe2 aria-hidden="true" /></span>
                    <span><strong>{source.publisher}</strong><span>{source.title}</span><small>{domain(source.url)} · {relativeTime(source.last_checked_at)}</small></span>
                  </a>
                  <div className="watch-source-state">
                    <ModeBadge mode={source.status} />
                    <small>{source.category ?? 'document'}{source.package ? ` · ${source.package}` : ''}</small>
                  </div>
                  {source.custom && <IconButton icon={Trash2} label={`Remove ${source.title}`} disabled={removing === source.id} onClick={() => void remove(source.id.replace(/^src-/, ''))} />}
                  {source.error && <p className="watch-source-error">{source.error}</p>}
                </article>
              ))}
            </div>
          ) : <EmptyState icon={Globe2} title="No inferred watches" description="Add a public URL above, or connect a repository with supported dependencies or model identifiers." />}
          <div className="watchlist-footnote"><Clock3 aria-hidden="true" /><span>Baselines persist across refreshes. Recent responses may be served from cache.</span></div>
        </section>
      </div>

      <section className="research-section">
        <SectionHeading
          title="Scoped web research"
          description="One Context.dev search per refresh, restricted to official provider domains."
          action={data.research?.mode ? <ModeBadge mode={data.research.mode} /> : <Search aria-hidden="true" />}
        />
        {data.research?.query && <div className="research-query"><span>Query</span><code>{data.research.query}</code><time>{relativeTime(data.research.retrieved_at ?? null)}</time></div>}
        {researchError && <InlineNotice tone="warning" role="status">{researchError}</InlineNotice>}
        {data.discoveries.length ? (
          <div className="discovery-grid">
            {data.discoveries.map((result) => (
              <a className="discovery-card" href={result.url} target="_blank" rel="noreferrer noopener" key={result.id}>
                <div><span>{domain(result.url)}</span><ArrowUpRight aria-hidden="true" /></div>
                <h3>{result.title}</h3>
                {result.summary && <p>{result.summary}</p>}
                {result.matched_terms.length > 0 && <div className="discovery-terms">{result.matched_terms.map((term) => <code key={term}>{term}</code>)}</div>}
                <small>Retrieved {formatDate(result.retrieved_at, true)}</small>
              </a>
            ))}
          </div>
        ) : (
          <div className="research-empty"><Search aria-hidden="true" /><p>{researchError ? 'No research has been retrieved for this query. See the request and budget status above.' : 'Research results will appear after a Context.dev refresh for a repository with supported models or dependencies.'}</p></div>
        )}
      </section>
    </div>
  );
}
