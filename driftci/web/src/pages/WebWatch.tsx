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
import { cx, domain, errorText, formatDate, plural, relativeTime } from '../utils';
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
  const sources = data.sources.filter((source) => source.watch || source.category);
  const usage = health?.context_dev.usage;
  const credits = usage?.daily_credits ?? 0;
  const limit = usage?.daily_credit_limit ?? 80;
  const cacheHours = Math.round((usage?.cache_ttl_seconds ?? 21600) / 3600);

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
            <p>Official pages are checked on a local polling schedule. A {cacheHours}-hour shared cache and daily credit ceiling keep refresh costs bounded.</p>
          </div>
        </div>
        <div className="context-budget">
          <span>Local usage today</span>
          <strong>{credits}<small> / {limit} credits</small></strong>
          <div className="budget-track" aria-label={`${credits} of ${limit} daily Context.dev credits used`}><span style={{ width: `${Math.min(100, credits / limit * 100)}%` }} /></div>
          <p>{plural(usage?.daily_queries ?? 0, 'live request')} today · {plural(data.metrics.context_queries, 'request')} recorded</p>
        </div>
      </section>

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
          <SectionHeading title="Watchlist" description="Inferred from installed packages and configured models." />
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
          <div className="research-empty"><Search aria-hidden="true" /><p>Research results will appear after a Context.dev refresh for a repository with supported models or dependencies.</p></div>
        )}
      </section>
    </div>
  );
}
