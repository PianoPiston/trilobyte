import {
  Activity as ActivityIcon,
  ArrowRight,
  Boxes,
  CheckCircle2,
  CircleDot,
  Clock3,
  Diff,
  FileDiff,
  FileSearch,
  Gauge,
  Globe2,
  Layers3,
  Radio,
  ScanSearch,
  ShieldAlert,
} from 'lucide-react';
import type { Bootstrap, Health, View } from '../types';
import { cx, formatDate, plural, relativeTime, severityRank } from '../utils';
import {
  Button,
  EmptyState,
  InlineNotice,
  ModeBadge,
  PageHeading,
  SectionHeading,
  SeverityBadge,
  StateBadge,
} from '../components/ui';

function ActivityIconFor({ type }: { type: string }) {
  if (type.includes('scan')) return <ScanSearch aria-hidden="true" />;
  if (type.includes('remediation') || type.includes('patch')) return <FileDiff aria-hidden="true" />;
  if (type.includes('incident') || type.includes('vulnerab')) return <ShieldAlert aria-hidden="true" />;
  if (type.includes('resolv')) return <CheckCircle2 aria-hidden="true" />;
  return <CircleDot aria-hidden="true" />;
}

export function MissionControl({ data, health, onNavigate, onSelectSignal }: {
  data: Bootstrap;
  health: Health | null;
  onNavigate: (view: View) => void;
  onSelectSignal: (id: string) => void;
}) {
  const queue = [...data.signals]
    .filter((signal) => signal.state !== 'resolved')
    .sort((a, b) => severityRank[a.severity] - severityRank[b.severity]);
  const maximumUsage = Math.max(1, ...data.dependencies.map((dependency) => dependency.usage_count));
  const osv = data.sources.find((source) => source.publisher === 'OSV');
  const latestChange = data.changes[0];
  const visibleDependencies = [...data.dependencies]
    .sort((a, b) => b.issues - a.issues || b.usage_count - a.usage_count || a.name.localeCompare(b.name))
    .slice(0, 8);

  return (
    <div className="page overview-page">
      <PageHeading
        eyebrow="Mission control"
        title="Live changes. Exact blast radius."
        description="The official web is watched through Context.dev, then each meaningful change is traced to the code your team owns."
        actions={<Button icon={Globe2} onClick={() => onNavigate('watch')}>Open web watch</Button>}
      />

      {data.workspace.coverage && !data.workspace.coverage.complete && (
        <div className="partial-scan-notice">
          <InlineNotice tone="warning" data-testid="partial-scan-notice">
            <div><strong>Bounded scan: {data.workspace.coverage.files_read} of {data.workspace.coverage.candidate_files} relevant files read.</strong><p>Findings are not evidence of absence in unread files. Review Repository coverage before relying on a zero-result summary.</p></div>
          </InlineNotice>
        </div>
      )}

      {!!osv?.packages_pending && (
        <div className="partial-scan-notice">
          <InlineNotice tone="warning" data-testid="partial-osv-notice">
            <div><strong>Vulnerability checks: {osv.packages_checked} / {osv.packages_total} exact packages.</strong><p>{osv.packages_pending} are pending the query budget or timed out. Findings are scoped to checked packages; unqueried packages are not certified safe.</p></div>
          </InlineNotice>
        </div>
      )}

      <section className="live-pulse" aria-label="Context.dev watch summary">
        <span className="pulse-symbol"><Radio aria-hidden="true" /></span>
        <div className="pulse-copy">
          <span>Live web memory · Context.dev</span>
          <strong>{latestChange ? latestChange.title : `${data.summary.watched_sources} official sources, each with a persistent baseline.`}</strong>
          <p>{latestChange ? `${latestChange.added_lines} additions and ${latestChange.removed_lines} removals observed ${relativeTime(latestChange.observed_at).toLowerCase()}.` : 'The next changed snapshot will appear with its diff and affected code locations.'}</p>
        </div>
        <div className="pulse-stat"><span>Changes observed</span><strong>{data.summary.observed_changes}</strong></div>
        <div className="pulse-stat"><span>Local credits today</span><strong>{health?.context_dev.usage.daily_credits ?? 0}</strong></div>
        <Button variant="ghost" onClick={() => onNavigate('watch')}>Watchlist<ArrowRight aria-hidden="true" /></Button>
      </section>

      <section className="metric-grid" aria-label="Workspace risk summary">
        <article className="metric-card risk-card">
          <div className="risk-gauge-small">
            <Gauge aria-hidden="true" />
          </div>
          <div>
            <span className="metric-label">Workspace risk</span>
            <div className="metric-value">{data.summary.risk_score}<span>/100</span></div>
            <p>{plural(data.summary.affected_dependencies, 'affected dependency', 'affected dependencies')}</p>
          </div>
          <div className="risk-meter" aria-hidden="true">
            <span style={{ width: `${Math.max(0, Math.min(100, data.summary.risk_score))}%` }} />
          </div>
        </article>
        <article className="metric-card">
          <div className="metric-icon tone-coral"><Layers3 aria-hidden="true" /></div>
          <span className="metric-label">Active changes</span>
          <div className="metric-value">{data.summary.active_changes}</div>
          <p>Signals awaiting review or action</p>
        </article>
        <article className="metric-card">
          <div className="metric-icon tone-coral"><ShieldAlert aria-hidden="true" /></div>
          <span className="metric-label">Critical vulnerabilities</span>
          <div className="metric-value">{data.summary.critical_vulnerabilities}</div>
          <p>{plural(data.incidents.length, 'active incident')}</p>
        </article>
        <article className="metric-card">
          <div className="metric-icon tone-mint"><Diff aria-hidden="true" /></div>
          <span className="metric-label">Web changes observed</span>
          <div className="metric-value">{data.summary.observed_changes}</div>
          <p>{plural(data.summary.watched_sources, 'watched source')} · persistent snapshots</p>
        </article>
      </section>

      <div className="overview-primary-grid">
        <section className="panel decision-panel">
          <SectionHeading
            title="Decision queue"
            description="Ranked by severity; open a signal for its repository evidence and next action."
            action={<span className="count-label">{plural(queue.length, 'open item')}</span>}
          />
          {queue.length ? (
            <div className="decision-list">
              {queue.slice(0, 5).map((signal) => (
                <button className="decision-item" key={signal.id} onClick={() => onSelectSignal(signal.id)}>
                  <span className={cx('decision-severity-line', `line-${signal.severity}`)} aria-hidden="true" />
                  <span className="decision-main">
                    <span className="decision-meta">
                      <SeverityBadge severity={signal.severity} />
                      <span>{signal.provider}</span>
                      <span>{signal.kind}</span>
                    </span>
                    <strong>{signal.title}</strong>
                    <span className="decision-summary">{signal.summary}</span>
                    <span className="decision-bottom">
                      <StateBadge state={signal.state} />
                      {signal.deadline && <span><Clock3 aria-hidden="true" />{formatDate(signal.deadline)}</span>}
                      {signal.evidence.length > 0 && <span><FileSearch aria-hidden="true" />{plural(signal.evidence.length, 'code location')}</span>}
                    </span>
                  </span>
                  <ArrowRight className="decision-arrow" aria-hidden="true" />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState icon={CheckCircle2} title="The decision queue is clear" description="New actionable source changes will appear here after a scan." />
          )}
          {queue.length > 0 && (
            <div className="panel-footer-link">
              <Button variant="ghost" onClick={() => onNavigate('radar')}>
                View all {plural(queue.length, 'signal')}<ArrowRight aria-hidden="true" />
              </Button>
            </div>
          )}
        </section>

        <section className="panel sources-panel">
          <SectionHeading title="Source health" description="Live, cached and replay states stay explicit." action={<Button variant="ghost" size="small" onClick={() => onNavigate('watch')}>Manage<ArrowRight aria-hidden="true" /></Button>} />
          {data.sources.length ? (
            <div className="source-status-list">
              {data.sources.map((source) => (
                <a className="source-status-item" href={source.url} target="_blank" rel="noreferrer noopener" key={source.id}>
                  <div className="source-symbol"><Globe2 aria-hidden="true" /></div>
                  <div className="source-status-copy">
                    <strong>{source.publisher}</strong>
                    <span>{source.title}</span>
                    <small>{relativeTime(source.last_checked_at)} · {plural(source.event_count, 'event')}</small>
                  </div>
                  <ModeBadge mode={source.status} />
                </a>
              ))}
            </div>
          ) : (
            <EmptyState icon={Globe2} title="No watched sources" description="Connect a repository or run a scan to populate source status." />
          )}
          <div className="source-legend">
            <span className="status-dot dot-live" />Live
            <span className="status-dot dot-cached" />Cached
            <span className="status-dot dot-replay" />Replay
          </div>
        </section>
      </div>

      <div className="overview-secondary-grid">
        <section className="panel dependency-panel">
          <SectionHeading title="Dependency blast radius" description={`${data.dependencies.length} packages indexed; highest-impact packages shown.`} action={<span className="count-label">Top {visibleDependencies.length}</span>} />
          {data.dependencies.length ? (
            <div className="dependency-table-wrap">
              <table className="dependency-table">
                <thead><tr><th>Package</th><th>Health</th><th>Repository usage</th><th>Issues</th></tr></thead>
                <tbody>
                  {visibleDependencies.map((dependency) => (
                    <tr key={`${dependency.ecosystem}:${dependency.name}`}>
                      <td>
                        <div className="package-name"><Boxes aria-hidden="true" /><code>{dependency.name}</code></div>
                        <span>{dependency.ecosystem} · {dependency.version} · {dependency.kind}</span>
                      </td>
                      <td><SeverityBadge severity={dependency.health} /></td>
                      <td>
                        <div className="usage-value">{dependency.usage_count}</div>
                        <div className="usage-track" aria-label={`${dependency.usage_count} indexed usages`}>
                          <span style={{ width: `${dependency.usage_count / maximumUsage * 100}%` }} />
                        </div>
                      </td>
                      <td><span className={cx('issue-count', dependency.issues > 0 && 'has-issues')}>{dependency.issues}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon={Boxes} title="No dependencies indexed" description="Dependency usage will appear after the repository scan completes." />
          )}
        </section>

        <section className="panel activity-panel">
          <SectionHeading title="Recent activity" description="Workspace and source events from the API." />
          {data.activity.length ? (
            <ol className="activity-list">
              {data.activity.slice(0, 6).map((event) => (
                <li key={event.id}>
                  <div className="activity-icon"><ActivityIconFor type={event.type} /></div>
                  <div>
                    <strong>{event.title}</strong>
                    <p>{event.detail}</p>
                    <time dateTime={event.created_at}>{relativeTime(event.created_at)}</time>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState icon={ActivityIcon} title="No activity yet" description="Refreshes, web changes and review activity will be recorded here." />
          )}
        </section>
      </div>

      <section className="operations-strip" aria-label="Response metrics">
        <div><Layers3 aria-hidden="true" /><span>Model identifiers</span><strong>{data.summary.production_models}</strong></div>
        <div><CheckCircle2 aria-hidden="true" /><span>Resolved this month</span><strong>{data.summary.resolved_this_month}</strong></div>
        <div><Clock3 aria-hidden="true" /><span>Mean response</span><strong>{data.summary.mean_response_hours} h</strong></div>
      </section>
    </div>
  );
}
