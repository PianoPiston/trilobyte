import {
  ArrowUpRight,
  CalendarClock,
  Crosshair,
  FileDiff,
  PackageCheck,
  Radar,
  ShieldAlert,
  WandSparkles,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Remediation, Signal } from '../types';
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

export function SignalDrawer({ signalId, initialSignal, remediations, onClose, onRemediate, onReview, onSignalUpdated }: {
  signalId: string;
  initialSignal?: Signal;
  remediations: Remediation[];
  onClose: () => void;
  onRemediate: (signalId: string) => Promise<Remediation>;
  onReview: (remediation: Remediation) => void;
  onSignalUpdated: (signal: Signal) => void;
}) {
  const [signal, setSignal] = useState<Signal | undefined>(initialSignal);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);
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

  const remediation = remediations.find((item) => item.signal_id === signalId);

  const generate = async () => {
    if (!signal) return;
    setGenerating(true);
    setError('');
    try {
      const result = await onRemediate(signal.id);
      const updated = { ...signal, state: 'fix_ready' as const, remediation_id: result.id };
      setSignal(updated);
      onSignalUpdated(updated);
      onReview(result);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setGenerating(false);
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
          <div className="drawer-footer-context"><Radar aria-hidden="true" /><span>Review evidence before applying any change.</span></div>
          <div className="dialog-footer-actions">
            {remediation ? (
              <Button variant="primary" icon={FileDiff} onClick={() => onReview(remediation)}>Review generated patch</Button>
            ) : signal.state !== 'resolved' ? (
              <Button variant="primary" icon={WandSparkles} loading={generating} onClick={() => void generate()}>
                {signal.state === 'fix_ready' ? 'Load remediation' : 'Generate targeted fix'}
              </Button>
            ) : null}
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
          {error && <InlineNotice tone="error" role="alert"><span>{error}</span><Button size="small" onClick={() => setRefreshKey((value) => value + 1)}>Retry</Button></InlineNotice>}

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
            <div className="signal-deadline-note"><CalendarClock aria-hidden="true" /><span>Deadline shown exactly as supplied by the signal: {formatDate(signal.deadline, true)}.</span></div>
          )}
        </>
      ) : null}
    </Drawer>
  );
}
