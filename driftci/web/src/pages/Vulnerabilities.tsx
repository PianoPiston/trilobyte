import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  Download,
  ExternalLink,
  FileDiff,
  History,
  ListChecks,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  WandSparkles,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import type {
  Bootstrap,
  Incident,
  IncidentsResponse,
  Remediation,
} from '../types';
import { cx, errorText, formatDate, relativeTime, responseDuration } from '../utils';
import {
  Button,
  CodeEvidence,
  EmptyState,
  ErrorState,
  InlineNotice,
  PageHeading,
  SectionHeading,
  SeverityBadge,
  SourceReceiptCard,
  Spinner,
  StateBadge,
} from '../components/ui';

function toReport(data: Bootstrap): IncidentsResponse {
  return {
    active: data.incidents,
    history: data.history,
    metrics: {
      active: data.incidents.length,
      critical: data.incidents.filter((incident) => incident.severity === 'critical').length,
      resolved: data.summary.resolved_this_month,
      mean_response_hours: data.summary.mean_response_hours,
    },
  };
}

function IncidentMetadata({ incident }: { incident: Incident }) {
  return (
    <div className="incident-facts">
      <div><span>Affected package</span><code>{incident.affected_package}@{incident.affected_version}</code></div>
      <div><span>Fixed version</span><code>{incident.fixed_version ?? 'No fix specified'}</code></div>
      <div><span>First seen</span><strong>{formatDate(incident.first_seen_at, true)}</strong></div>
      <div><span>Reachability clue</span><strong>{incident.reachability}</strong></div>
    </div>
  );
}

export function Vulnerabilities({ data, remediations, onIncidentUpdated, onRemediate, onReview }: {
  data: Bootstrap;
  remediations: Remediation[];
  onIncidentUpdated: (incident: Incident) => void;
  onRemediate: (signalId: string) => Promise<Remediation>;
  onReview: (remediation: Remediation) => void;
}) {
  const [report, setReport] = useState<IncidentsResponse>(() => toReport(data));
  const [tab, setTab] = useState<'active' | 'history'>('active');
  const [selectedId, setSelectedId] = useState(data.incidents[0]?.id ?? '');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [updatingAction, setUpdatingAction] = useState('');
  const [generating, setGenerating] = useState(false);
  const [reporting, setReporting] = useState('');

  const refresh = useCallback(async (abort?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.incidents(abort);
      if (!abort?.aborted) setReport(result);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      if (!abort?.aborted) setError(errorText(requestError));
    } finally {
      if (!abort?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    setReport(toReport(data));
  }, [data]);

  useEffect(() => {
    if (!report.active.some((incident) => incident.id === selectedId)) {
      setSelectedId(report.active[0]?.id ?? '');
    }
  }, [report.active, selectedId]);

  const selected = report.active.find((incident) => incident.id === selectedId) ?? report.active[0];

  const toggleAction = async (incident: Incident, actionId: string, currentStatus: 'done' | 'pending') => {
    const key = `${incident.id}:${actionId}`;
    setUpdatingAction(key);
    setActionError('');
    try {
      const updated = await api.setIncidentAction(incident.id, actionId, currentStatus === 'done' ? 'pending' : 'done');
      onIncidentUpdated(updated);
      setReport((current) => ({
        ...current,
        active: current.active.map((item) => item.id === updated.id ? updated : item),
        history: current.history.map((item) => item.id === updated.id ? updated : item),
      }));
      await refresh();
    } catch (requestError) {
      setActionError(errorText(requestError));
    } finally {
      setUpdatingAction('');
    }
  };

  const remediate = async (incident: Incident) => {
    if (!incident.signal_id) return;
    setGenerating(true);
    setActionError('');
    try {
      await onRemediate(incident.signal_id);
    } catch (requestError) {
      setActionError(errorText(requestError));
    } finally {
      setGenerating(false);
    }
  };

  const exportReport = async (incident: Incident) => {
    setReporting(incident.id);
    setActionError('');
    try {
      const markdown = await api.incidentReport(incident.id);
      const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${incident.cve}-incident.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setActionError(errorText(requestError));
    } finally {
      setReporting('');
    }
  };

  return (
    <div className="page vulnerabilities-page">
      <PageHeading
        eyebrow="Vulnerability response"
        title="Work the incident, not just the CVE."
        description="Advisory context, repository reachability clues and an accountable response checklist."
        actions={<Button icon={RefreshCw} loading={loading} onClick={() => void refresh()}>Refresh incidents</Button>}
      />

      <section className="incident-metrics" aria-label="Incident metrics">
        <div><Siren aria-hidden="true" /><span>Active</span><strong>{report.metrics.active}</strong></div>
        <div><ShieldAlert aria-hidden="true" /><span>Critical</span><strong>{report.metrics.critical}</strong></div>
        <div><ShieldCheck aria-hidden="true" /><span>Resolved</span><strong>{report.metrics.resolved}</strong></div>
        <div><Clock3 aria-hidden="true" /><span>Mean response</span><strong>{report.metrics.mean_response_hours} h</strong></div>
      </section>

      <div className="tab-bar" role="tablist" aria-label="Incident views">
        <button role="tab" aria-selected={tab === 'active'} className={cx(tab === 'active' && 'active')} onClick={() => setTab('active')}>
          Active incidents<span>{report.active.length}</span>
        </button>
        <button role="tab" aria-selected={tab === 'history'} className={cx(tab === 'history' && 'active')} onClick={() => setTab('history')}>
          CVE history<span>{report.history.length}</span>
        </button>
      </div>

      {error && !loading && (
        <InlineNotice tone="error" role="alert"><span>{error}</span><Button size="small" onClick={() => void refresh()}>Retry</Button></InlineNotice>
      )}
      {loading && report.active.length === 0 && report.history.length === 0 ? (
        <div className="panel loading-panel"><Spinner label="Loading vulnerability intelligence" /></div>
      ) : error && report.active.length === 0 && report.history.length === 0 ? (
        <ErrorState message={error} onRetry={() => void refresh()} />
      ) : tab === 'active' ? (
        report.active.length === 0 ? (
          <div className="panel"><EmptyState icon={ShieldCheck} title="No active incidents" description="The API has no active vulnerability incidents for this workspace. Resolved advisories remain in CVE history." action={<Button onClick={() => setTab('history')}>View history</Button>} /></div>
        ) : (
          <div className="incident-layout">
            <aside className="incident-list" aria-label="Active incidents">
              {report.active.map((incident) => (
                <button
                  key={incident.id}
                  className={cx('incident-list-item', selected?.id === incident.id && 'selected')}
                  onClick={() => setSelectedId(incident.id)}
                  aria-pressed={selected?.id === incident.id}
                >
                  <span className="incident-list-top"><SeverityBadge severity={incident.severity} /><code>{incident.cve}</code></span>
                  <strong>{incident.title}</strong>
                  <span className="incident-package"><PackageCheck aria-hidden="true" />{incident.affected_package}@{incident.affected_version}</span>
                  <span className="incident-list-bottom">
                    <span>{incident.cvss ?? '—'} CVSS</span><span>{relativeTime(incident.first_seen_at)}</span><ArrowRight aria-hidden="true" />
                  </span>
                </button>
              ))}
            </aside>

            {selected && (
              <section className="incident-detail">
                <div className="incident-detail-header">
                  <div className="incident-detail-badges">
                    <SeverityBadge severity={selected.severity} />
                    <StateBadge state={selected.state} />
                    {selected.kev && <span className="badge kev-badge"><AlertTriangle aria-hidden="true" />CISA KEV</span>}
                  </div>
                  <code className="cve-identifier">{selected.cve}</code>
                  <h2>{selected.title}</h2>
                  <p>{selected.summary}</p>
                  <div className="cvss-row">
                    <div className="cvss-score"><strong>{selected.cvss ?? '—'}</strong><span>CVSS</span></div>
                    <div><span>CISA Known Exploited Vulnerabilities</span><strong>{selected.kev ? 'Listed' : 'Not listed'}</strong></div>
                  </div>
                </div>

                <IncidentMetadata incident={selected} />

                <InlineNotice tone="warning" className="reachability-note">
                  <AlertTriangle aria-hidden="true" />
                  <div><strong>{selected.reachability} reachability is a repository heuristic.</strong><p>{selected.reachability_reason}</p><small>Installation alone does not establish exploitability. Verify deployment behavior.</small></div>
                </InlineNotice>

                <div className="incident-fix-bar">
                  <div><FileDiff aria-hidden="true" /><span>Targeted remediation</span><small>Generate a reviewable patch with checks and citations.</small></div>
                  <Button icon={Download} loading={reporting === selected.id} onClick={() => void exportReport(selected)}>Export IR record</Button>
                  {selected.signal_id && (() => {
                    const existing = remediations.find((item) => item.signal_id === selected.signal_id);
                    return existing ? (
                      <Button icon={FileDiff} onClick={() => onReview(existing)}>Review patch</Button>
                    ) : (
                      <Button variant="primary" icon={WandSparkles} loading={generating} onClick={() => void remediate(selected)}>Generate fix</Button>
                    );
                  })()}
                </div>

                {actionError && <InlineNotice tone="error" role="alert">{actionError}</InlineNotice>}

                <section className="response-checklist">
                  <SectionHeading title="Incident response" description="Completed steps are timestamped by the backend. Toggle a step to reopen it." action={<ListChecks aria-hidden="true" />} />
                  <ol>
                    {selected.actions.map((action, index) => {
                      const done = action.status === 'done';
                      const key = `${selected.id}:${action.id}`;
                      return (
                        <li className={cx(done && 'completed')} key={action.id}>
                          <button
                            className="check-action"
                            aria-label={`${done ? 'Reopen' : 'Complete'}: ${action.label}`}
                            aria-pressed={done}
                            disabled={updatingAction === key}
                            onClick={() => void toggleAction(selected, action.id, action.status)}
                          >
                            {updatingAction === key ? <RefreshCw className="spin" aria-hidden="true" /> : done ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}
                          </button>
                          <div className="checklist-index">{String(index + 1).padStart(2, '0')}</div>
                          <div className="checklist-copy">
                            <strong>{action.label}</strong>
                            <p>{action.detail}</p>
                            {action.completed_at && <time dateTime={action.completed_at}><CheckCircle2 aria-hidden="true" />{formatDate(action.completed_at, true)}</time>}
                          </div>
                          <StateBadge state={action.status} />
                        </li>
                      );
                    })}
                  </ol>
                </section>

                <section className="incident-evidence-section">
                  <SectionHeading title="Repository reachability clues" description="Locations returned by repository analysis." />
                  <CodeEvidence evidence={selected.affected_files} />
                </section>

                {selected.source_receipts.length > 0 && (
                  <section className="incident-evidence-section">
                    <SectionHeading title="Advisory receipts" description="Primary vulnerability intelligence for this incident." />
                    <div className="receipt-grid">
                      {selected.source_receipts.map((receipt, index) => <SourceReceiptCard key={`${receipt.url}:${index}`} receipt={receipt} compact />)}
                    </div>
                  </section>
                )}
              </section>
            )}
          </div>
        )
      ) : (
        <section className="history-section">
          {report.history.length === 0 ? (
            <div className="panel"><EmptyState icon={History} title="No resolved CVE history" description="Resolved vulnerability incidents will remain available here with their response timeline." /></div>
          ) : (
            <div className="history-list">
              {report.history.map((incident) => (
                <article className="history-card" key={incident.id}>
                  <div className="history-status"><CheckCircle2 aria-hidden="true" /><span>Resolved</span></div>
                  <div className="history-main">
                    <div><SeverityBadge severity={incident.severity} /><code>{incident.cve}</code>{incident.kev && <span className="badge kev-badge">CISA KEV</span>}</div>
                    <h2>{incident.title}</h2>
                    <p>{incident.affected_package}@{incident.affected_version} → {incident.fixed_version ?? 'documented resolution'}</p>
                  </div>
                  <div className="history-timing">
                    <strong>{responseDuration(incident.first_seen_at, incident.resolved_at) ?? 'Response time unavailable'}</strong>
                    <span>Resolved {formatDate(incident.resolved_at, true)}</span>
                  </div>
                  <details>
                    <summary>Incident record<ExternalLink aria-hidden="true" /></summary>
                    <div className="history-record">
                      <Button icon={Download} loading={reporting === incident.id} onClick={() => void exportReport(incident)}>Export incident report</Button>
                      <p>{incident.summary}</p>
                      <IncidentMetadata incident={incident} />
                      <CodeEvidence evidence={incident.affected_files} />
                      {incident.source_receipts.map((receipt, index) => <SourceReceiptCard key={`${receipt.url}:${index}`} receipt={receipt} compact />)}
                    </div>
                  </details>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
