import {
  Archive,
  ArrowUpRight,
  CalendarClock,
  CheckCheck,
  Crosshair,
  Diff,
  PackageCheck,
  Radar,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Signal } from '../types';
import { errorText, formatDate, label, plural } from '../utils';
import {
  Button,
  CodeEvidence,
  Drawer,
  EmptyState,
  ErrorState,
  InlineNotice,
  SeverityBadge,
  SourceReceiptCard,
  Spinner,
  StateBadge,
} from './ui';

export function SignalDrawer({ signalId, initialSignal, onClose, onSignalUpdated }: {
  signalId: string;
  initialSignal?: Signal;
  onClose: () => void;
  onSignalUpdated: (signal: Signal) => void;
}) {
  const [signal, setSignal] = useState<Signal | undefined>(initialSignal);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updating, setUpdating] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setSignal(initialSignal);
    setLoading(true);
    setError('');
    api.signal(signalId)
      .then((result) => { if (!controller.signal.aborted) setSignal(result); })
      .catch((requestError: unknown) => { if (!controller.signal.aborted) setError(errorText(requestError)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [signalId, initialSignal, refreshKey]);

  const updateState = async (state: 'acknowledged' | 'resolved') => {
    if (!signal) return;
    setUpdating(state);
    setError('');
    try {
      const updated = await api.setSignalState(signal.id, state);
      setSignal(updated);
      onSignalUpdated(updated);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setUpdating('');
    }
  };

  return (
    <Drawer
      title={signal?.title ?? 'Signal details'}
      subtitle={signal ? `${signal.provider} · ${label(signal.kind)}` : signalId}
      onClose={onClose}
      wide
      footer={signal ? (
        <>
          <div className="drawer-footer-context"><Radar aria-hidden="true" /><span>Review the source and code evidence before closing the loop.</span></div>
          <div className="dialog-footer-actions">
            {signal.state !== 'acknowledged' && signal.state !== 'resolved' && (
              <Button icon={CheckCheck} loading={updating === 'acknowledged'} onClick={() => void updateState('acknowledged')}>Mark reviewed</Button>
            )}
            {signal.state !== 'resolved' && signal.kind !== 'vulnerability' && (
              <Button variant="primary" icon={Archive} loading={updating === 'resolved'} onClick={() => void updateState('resolved')}>Resolve</Button>
            )}
          </div>
        </>
      ) : undefined}
    >
      {loading && !signal ? <Spinner label="Loading signal evidence" /> : error && !signal ? (
        <ErrorState message={error} onRetry={() => setRefreshKey((value) => value + 1)} />
      ) : signal ? (
        <>
          <div className="signal-detail-status">
            <SeverityBadge severity={signal.severity} />
            <StateBadge state={signal.state} />
            {signal.kev && <span className="badge kev-badge"><ShieldAlert aria-hidden="true" />CISA KEV</span>}
            {loading && <span className="subtle-loading">Refreshing evidence…</span>}
          </div>
          {error && <InlineNotice tone="error" role="alert"><span>{error}</span></InlineNotice>}

          <section className="signal-detail-intro">
            <p className="signal-detail-summary">{signal.summary}</p>
            <div className="recommendation-block">
              <Crosshair aria-hidden="true" />
              <div><span>Recommended next action</span><p>{signal.recommendation}</p></div>
            </div>
          </section>

          <dl className="signal-fact-grid">
            <div><dt>Provider</dt><dd>{signal.provider}</dd></div>
            <div><dt>Signal created</dt><dd>{formatDate(signal.created_at, true)}</dd></div>
            <div><dt>Deadline</dt><dd>{signal.deadline ? formatDate(signal.deadline, true) : 'No deadline supplied'}</dd></div>
            {signal.replacement && <div><dt>Replacement</dt><dd><code>{signal.replacement}</code></dd></div>}
            {signal.fixed_version && <div><dt>Fixed version</dt><dd><code>{signal.fixed_version}</code></dd></div>}
            {signal.cve && <div><dt>CVE</dt><dd><code>{signal.cve}</code></dd></div>}
            {signal.cvss !== null && <div><dt>CVSS</dt><dd>{signal.cvss}</dd></div>}
            {signal.reachability && <div><dt>Repository reachability</dt><dd>{label(signal.reachability)}</dd></div>}
          </dl>

          {signal.reachability && <p className="heuristic-caption">Reachability describes repository clues. Confirm exploitability against the deployed application.</p>}

          {signal.change && (
            <section className="drawer-section">
              <div className="drawer-section-heading"><h3>Observed page diff</h3><span><Diff aria-hidden="true" /> +{signal.change.added_lines} / −{signal.change.removed_lines}</span></div>
              <div className="web-diff-preview expanded">
                {signal.change.removed.map((line, index) => <div className="web-diff-line removed" key={`r${index}`}><span>−</span><code>{line}</code></div>)}
                {signal.change.added.map((line, index) => <div className="web-diff-line added" key={`a${index}`}><span>+</span><code>{line}</code></div>)}
              </div>
              <p className="heuristic-caption">Compared with snapshot {signal.change.previous_hash.slice(0, 12)}. The current snapshot is {signal.change.content_hash.slice(0, 12)}.</p>
            </section>
          )}

          {signal.affected_assets.length > 0 && (
            <section className="drawer-section">
              <div className="drawer-section-heading"><h3>Affected production assets</h3><span>{plural(signal.affected_assets.length, 'asset')}</span></div>
              <div className="asset-list">{signal.affected_assets.map((asset) => <span key={asset}><PackageCheck aria-hidden="true" />{asset}</span>)}</div>
            </section>
          )}

          <section className="drawer-section">
            <div className="drawer-section-heading"><h3>Source-to-code evidence</h3><span>{plural(signal.evidence.length, 'location')}</span></div>
            <CodeEvidence evidence={signal.evidence} />
          </section>

          <section className="drawer-section">
            <div className="drawer-section-heading"><h3>Primary source receipts</h3><span>{plural(signal.source_receipts.length, 'receipt')}</span></div>
            {signal.source_receipts.length ? (
              <div className="receipt-stack">
                {signal.source_receipts.map((receipt, index) => <SourceReceiptCard key={`${receipt.url}:${index}`} receipt={receipt} />)}
              </div>
            ) : <EmptyState icon={ArrowUpRight} title="No source receipts returned" description="This signal has no primary-source receipt. Treat its provenance as incomplete." />}
          </section>

          {signal.deadline && (
            <div className="signal-deadline-note"><CalendarClock aria-hidden="true" /><span>Deadline supplied by the source: {formatDate(signal.deadline, true)}.</span></div>
          )}
        </>
      ) : null}
    </Drawer>
  );
}
