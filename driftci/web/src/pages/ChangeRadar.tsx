import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  FileDiff,
  FileSearch,
  FilterX,
  Radar,
  Search,
  ShieldCheck,
  WandSparkles,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type { Remediation, Signal, SignalKind, Severity } from '../types';
import { cx, errorText, formatDate, plural } from '../utils';
import {
  Button,
  EmptyState,
  ErrorState,
  InlineNotice,
  PageHeading,
  SeverityBadge,
  Spinner,
  StateBadge,
} from '../components/ui';

const kinds: SignalKind[] = ['deprecation', 'vulnerability', 'api', 'pricing', 'status'];
const severities: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

export function ChangeRadar({ initialSignals, remediations, onSelectSignal, onRemediate, onReview }: {
  initialSignals: Signal[];
  remediations: Remediation[];
  onSelectSignal: (id: string) => void;
  onRemediate: (signalId: string) => Promise<Remediation>;
  onReview: (remediation: Remediation) => void;
}) {
  const [signals, setSignals] = useState(initialSignals);
  const [kind, setKind] = useState('');
  const [severity, setSeverity] = useState('');
  const [state, setState] = useState('');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState('');

  const loadSignals = useCallback(async (abort?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.signals(kind, severity, abort);
      if (!abort?.aborted) setSignals(result);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      if (!abort?.aborted) setError(errorText(requestError));
    } finally {
      if (!abort?.aborted) setLoading(false);
    }
  }, [kind, severity]);

  useEffect(() => {
    setSignals(initialSignals);
  }, [initialSignals]);

  useEffect(() => {
    const controller = new AbortController();
    void loadSignals(controller.signal);
    return () => controller.abort();
  }, [loadSignals, initialSignals]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return signals.filter((signal) => {
      if (state && signal.state !== state) return false;
      if (!normalized) return true;
      return [signal.title, signal.summary, signal.provider, signal.cve ?? '', ...signal.affected_assets]
        .some((value) => value.toLowerCase().includes(normalized));
    });
  }, [signals, query, state]);

  const filtersActive = Boolean(kind || severity || state || query);
  const clearFilters = () => {
    setKind('');
    setSeverity('');
    setState('');
    setQuery('');
  };

  const remediate = async (signalId: string) => {
    setGenerating(signalId);
    setError('');
    try {
      await onRemediate(signalId);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setGenerating('');
    }
  };

  return (
    <div className="page radar-page">
      <PageHeading
        eyebrow="Change radar"
        title="Follow the signal to the source."
        description="Model, API, pricing and deprecation events with exact repository evidence."
        actions={<div className="evidence-principle"><ShieldCheck aria-hidden="true" /><span>Primary sources only</span></div>}
      />

      <section className="filter-bar" aria-label="Signal filters">
        <label className="search-field">
          <span className="sr-only">Search signals</span>
          <Search aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search provider, CVE or affected asset" />
        </label>
        <label>
          <span className="sr-only">Filter by kind</span>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">All kinds</option>
            {kinds.map((value) => <option value={value} key={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by severity</span>
          <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="">All severities</option>
            {severities.map((value) => <option value={value} key={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by state</span>
          <select value={state} onChange={(event) => setState(event.target.value)}>
            <option value="">All states</option>
            <option value="needs_action">Needs action</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="fix_ready">Fix ready</option>
            <option value="monitoring">Monitoring</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
        {filtersActive && <Button variant="ghost" size="small" icon={FilterX} onClick={clearFilters}>Clear filters</Button>}
      </section>

      <div className="results-bar">
        <span>{loading ? 'Refreshing signals…' : plural(filtered.length, 'signal')}</span>
        {(kind || severity) && <span>Server-filtered results</span>}
      </div>

      {error && signals.length > 0 && (
        <InlineNotice tone="error" role="alert">
          <span>{error}</span><Button size="small" onClick={() => void loadSignals()}>Retry</Button>
        </InlineNotice>
      )}
      {error && signals.length === 0 ? (
        <ErrorState message={error} onRetry={() => void loadSignals()} />
      ) : loading && signals.length === 0 ? (
        <div className="panel loading-panel"><Spinner label="Loading change signals" /></div>
      ) : filtered.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={filtersActive ? FilterX : CheckCircle2}
            title={filtersActive ? 'No signals match these filters' : 'No change signals returned'}
            description={filtersActive ? 'Adjust the search or clear filters to see the full radar.' : 'Run a scan to check the official sources for new events.'}
            action={filtersActive ? <Button icon={FilterX} onClick={clearFilters}>Clear filters</Button> : undefined}
          />
        </div>
      ) : (
        <div className={cx('signal-list', loading && 'list-refreshing')} aria-busy={loading}>
          {filtered.map((signal) => {
            const remediation = remediations.find((item) => item.signal_id === signal.id);
            return (
              <article className="signal-row" key={signal.id}>
                <button className="signal-row-main" onClick={() => onSelectSignal(signal.id)}>
                  <span className={cx('signal-rail', `line-${signal.severity}`)} aria-hidden="true" />
                  <span className="signal-heading-line">
                    <SeverityBadge severity={signal.severity} />
                    <span className="signal-provider">{signal.provider}</span>
                    <span className="signal-kind">{signal.kind}</span>
                    <StateBadge state={signal.state} />
                  </span>
                  <strong>{signal.title}</strong>
                  <span className="signal-summary">{signal.summary}</span>
                  <span className="signal-assets">
                    {signal.affected_assets.map((asset) => <span key={asset}>{asset}</span>)}
                  </span>
                  <span className="signal-row-meta">
                    {signal.deadline && <span><CalendarClock aria-hidden="true" />Deadline {formatDate(signal.deadline)}</span>}
                    <span><FileSearch aria-hidden="true" />{plural(signal.evidence.length, 'repository clue')}</span>
                    <span><Radar aria-hidden="true" />{plural(signal.source_receipts.length, 'source receipt')}</span>
                  </span>
                </button>
                <div className="signal-row-actions">
                  {remediation ? (
                    <Button size="small" icon={FileDiff} onClick={() => onReview(remediation)}>Review patch</Button>
                  ) : signal.state !== 'resolved' ? (
                    <Button
                      size="small"
                      icon={WandSparkles}
                      loading={generating === signal.id}
                      onClick={() => void remediate(signal.id)}
                    >
                      {signal.state === 'fix_ready' ? 'Load patch' : 'Generate patch'}
                    </Button>
                  ) : null}
                  <Button variant="ghost" size="small" onClick={() => onSelectSignal(signal.id)} aria-label={`Inspect ${signal.title}`}>
                    Inspect<ArrowRight aria-hidden="true" />
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
