import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  CheckCircle2,
  CircleDot,
  ClipboardCheck,
  Clock3,
  Download,
  ExternalLink,
  FileCode2,
  FileDiff,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequestArrow,
  Globe2,
  History,
  Pause,
  Radio,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { api } from '../api';
import type { Bootstrap, Health, PullRequest, ReleaseEvent, View } from '../types';
import { cx, errorText, formatDate, label, plural, relativeTime } from '../utils';
import {
  Button,
  CodeEvidence,
  Drawer,
  EmptyState,
  InlineNotice,
  PageHeading,
  SectionHeading,
  SeverityBadge,
  SourceReceiptCard,
  StateBadge,
} from '../components/ui';

const readiness: Record<string, { title: string; detail: string; tone: string }> = {
  needs_review: { title: 'Review external evidence', detail: 'Relevant official or advisory evidence is attached to this change.', tone: 'attention' },
  review_stale: { title: 'External evidence postdates approval', detail: 'A later web observation needs review against this PR.', tone: 'attention' },
  evidence_stale: { title: 'Release evidence changed', detail: 'The previous local decision covers different external facts or check results.', tone: 'attention' },
  head_changed: { title: 'Head changed since decision', detail: 'The previous local decision covers a different commit.', tone: 'attention' },
  checks_failed: { title: 'Checks need attention', detail: 'A failing or cancelled check is attached to this head.', tone: 'attention' },
  checks_running: { title: 'Checks running', detail: 'The latest head is waiting for CI.', tone: 'waiting' },
  paused: { title: 'Release paused locally', detail: 'The decision owner paused this exact head and evidence set.', tone: 'waiting' },
  ready: { title: 'Ready evidence recorded', detail: 'A named reviewer accepted this exact head and evidence set.', tone: 'ready' },
  merged: { title: 'Merged', detail: 'GitHub reports this pull request as merged.', tone: 'ready' },
  closed: { title: 'Closed', detail: 'GitHub reports this pull request as closed without merge.', tone: 'waiting' },
  observing: { title: 'Watching for external impact', detail: 'No matching external evidence was found in the bounded mapping.', tone: 'neutral' },
};

function readinessFor(pr: PullRequest) {
  return readiness[pr.readiness] ?? { title: label(pr.readiness), detail: 'Inspect this pull request and its source evidence.', tone: 'neutral' };
}

function CheckState({ state }: { state: string }) {
  if (state === 'passed') return <span className="release-check check-passed"><CheckCircle2 aria-hidden="true" />Checks passed</span>;
  if (state === 'pending') return <span className="release-check check-pending"><RefreshCw aria-hidden="true" />Checks running</span>;
  if (state === 'failed') return <span className="release-check check-failed"><XCircle aria-hidden="true" />Checks failing</span>;
  return <span className="release-check"><CircleDot aria-hidden="true" />No checks reported</span>;
}

function ReleaseCard({ pr, onOpen, onSelectSignal }: {
  pr: PullRequest;
  onOpen: (id: string) => void;
  onSelectSignal: (id: string) => void;
}) {
  const state = readinessFor(pr);
  return (
    <article className={cx('release-card', `release-card-${state.tone}`)}>
      <div className="release-card-topline">
        <span className="release-pr-number"><GitPullRequestArrow aria-hidden="true" />PR #{pr.number}</span>
        <span className="release-author"><span aria-hidden="true">{pr.author.slice(0, 2).toUpperCase()}</span>{pr.author}</span>
        {pr.draft && <span className="badge">Draft</span>}
        <time dateTime={pr.updated_at}>{relativeTime(pr.updated_at)}</time>
      </div>
      <a className="release-card-title" href={pr.url} target="_blank" rel="noreferrer noopener">{pr.title}<ArrowUpRight aria-hidden="true" /></a>
      <div className="release-branch"><GitBranch aria-hidden="true" /><code>{pr.base_ref}</code><span>←</span><code>{pr.head_ref}</code></div>

      <div className={cx('release-readiness', `readiness-${state.tone}`)}>
        <span className="release-readiness-marker" aria-hidden="true" />
        <div><strong>{state.title}</strong><p>{state.detail}</p></div>
        <code>{pr.head_sha.slice(0, 8)}</code>
      </div>

      <div className="release-evidence-list">
        {pr.external_evidence.slice(0, 3).map((evidence) => (
          <button key={evidence.id} className="release-evidence-link" onClick={() => onSelectSignal(evidence.id)}>
            <Globe2 aria-hidden="true" />
            <span><strong>{evidence.title}</strong><small>{evidence.provider} · {evidence.observed_at ? `Observed ${relativeTime(evidence.observed_at).toLowerCase()}` : 'Source baseline'}</small></span>
            <ArrowRight aria-hidden="true" />
          </button>
        ))}
      </div>
      {!pr.external_evidence.length && !pr.detail_complete && <p className="release-coverage-note">External mapping awaits this PR’s bounded file detail.</p>}

      <div className="release-card-footer">
        <span><CheckState state={pr.check_summary.state} /></span>
        <span>{plural(pr.changed_files, 'changed file')}{!pr.files_complete && ' · bounded'}</span>
        <Button size="small" onClick={() => onOpen(pr.id)}>Inspect release<ArrowRight aria-hidden="true" /></Button>
      </div>
    </article>
  );
}

function eventDestination(event: ReleaseEvent, onSelectSignal: (id: string) => void, onOpenPr: (id: string) => void) {
  if (event.signal_id) return () => onSelectSignal(event.signal_id ?? '');
  if (event.pr_id) return () => onOpenPr(event.pr_id ?? '');
  return undefined;
}

function ActivityFeed({ events, onSelectSignal, onOpenPr, onNavigate }: {
  events: ReleaseEvent[];
  onSelectSignal: (id: string) => void;
  onOpenPr: (id: string) => void;
  onNavigate: (view: View) => void;
}) {
  const [filter, setFilter] = useState<'all' | 'github' | 'web' | 'decisions'>('all');
  const rows = events.filter((event) => filter === 'all'
    || (filter === 'web' && event.kind === 'web_change')
    || (filter === 'decisions' && event.kind === 'decision')
    || (filter === 'github' && !['web_change', 'decision'].includes(event.kind))).reverse();
  return (
    <section className="panel release-activity-panel">
      <SectionHeading title="Live event memory" description="Verified arrivals, with initial imports marked as baselines." action={<Radio aria-hidden="true" />} />
      <div className="release-activity-filters" aria-label="Event filters">
        {(['all', 'github', 'web', 'decisions'] as const).map((value) => (
          <button key={value} aria-pressed={filter === value} className={cx(filter === value && 'active')} onClick={() => setFilter(value)}>{value === 'all' ? 'All' : value === 'web' ? 'Official web' : value === 'github' ? 'GitHub' : 'Decisions'}</button>
        ))}
      </div>
      {rows.length ? (
        <ol className="release-activity-list">
          {rows.map((event) => {
            const open = eventDestination(event, onSelectSignal, onOpenPr);
            const content = <>
              <span className={cx('release-event-marker', event.baseline && 'baseline')} aria-hidden="true" />
              <div>
                <span className="release-event-source">{event.source}<time dateTime={event.occurred_at}>{relativeTime(event.occurred_at)}</time></span>
                <strong>{event.title}</strong>
                <p>{event.detail}</p>
                <span className="release-event-meta">{event.baseline ? 'Initial baseline' : 'Observed event'}{event.pr_number ? ` · PR #${event.pr_number}` : ''}</span>
              </div>
              {(open || event.url) && <ArrowUpRight aria-hidden="true" />}
            </>;
            return <li key={event.seq} className={cx('release-activity-item', !event.baseline && 'release-live-event')}>
              {open ? <button onClick={open}>{content}</button> : event.url ? <a href={event.url} target="_blank" rel="noreferrer noopener">{content}</a> : <div>{content}</div>}
            </li>;
          })}
        </ol>
      ) : (
        <EmptyState icon={History} title="Waiting for release events" description="New GitHub activity and changed external snapshots will appear here without a page reload." />
      )}
      <div className="release-activity-footer"><button onClick={() => onNavigate('watch')}><Globe2 aria-hidden="true" />Inspect Context.dev watchlist<ArrowRight aria-hidden="true" /></button></div>
    </section>
  );
}

function downloadReport(markdown: string, number: number) {
  const objectUrl = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `pr-${number}-release-decision.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

export function ReleaseDrawer({ pr, onClose, onSelectSignal, onRecord }: {
  pr: PullRequest;
  onClose: () => void;
  onSelectSignal: (id: string) => void;
  onRecord: (id: string) => void;
}) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const state = readinessFor(pr);
  const exportDecision = async () => {
    setExporting(true);
    setError('');
    try {
      downloadReport(await api.releaseReport(pr.id), pr.number);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setExporting(false);
    }
  };
  const reviews = [...pr.reviews].sort((a, b) => (b.submitted_at ?? '').localeCompare(a.submitted_at ?? ''));
  return (
    <Drawer
      title={`PR #${pr.number} · ${pr.title}`}
      subtitle={`${pr.repository} · ${pr.base_ref} ← ${pr.head_ref}`}
      onClose={onClose}
      wide
      footer={<>
        <span className="release-drawer-scope"><ShieldCheck aria-hidden="true" />Local decision scope · {pr.head_sha.slice(0, 8)} / {pr.evidence_hash.slice(0, 8)}</span>
        <div className="dialog-footer-actions">
          {pr.state === 'open' && <Button variant="primary" icon={ClipboardCheck} onClick={() => onRecord(pr.id)}>Record decision</Button>}
        </div>
      </>}
    >
      <div className={cx('release-detail-banner', `readiness-${state.tone}`)}>
        <div><span>Release readiness</span><h3>{state.title}</h3><p>{state.detail}</p></div>
        <StateBadge state={pr.state} />
      </div>
      {pr.latest_external_observation && (
        <div className="release-freshness-comparison">
          <div><span>Latest external observation</span><strong>{formatDate(pr.latest_external_observation, true)}</strong></div>
          <span className="freshness-arrow" aria-hidden="true">→</span>
          <div><span>Latest retrieved GitHub approval</span><strong>{pr.latest_remote_approval ? formatDate(pr.latest_remote_approval, true) : 'No retrieved approval'}</strong></div>
        </div>
      )}
      {error && <InlineNotice tone="error" role="alert">{error}</InlineNotice>}
      <dl className="release-fact-grid">
        <div><dt>Head commit</dt><dd><code>{pr.head_sha}</code></dd></div>
        <div><dt>Evidence snapshot</dt><dd><code>{pr.evidence_hash}</code></dd></div>
        <div><dt>Last updated</dt><dd>{formatDate(pr.updated_at, true)}</dd></div>
        <div><dt>Changed-file coverage</dt><dd>{pr.files_complete ? 'Complete within declared bound' : 'Partial or awaiting detail'}</dd></div>
      </dl>

      {pr.expired_release_decision && (
        <InlineNotice tone="warning" className="release-expired-notice">
          <History aria-hidden="true" /><div><strong>Earlier {pr.expired_release_decision.decision} decision is no longer current.</strong><p>{pr.expired_release_decision.reviewer} recorded it {relativeTime(pr.expired_release_decision.created_at).toLowerCase()} for head {pr.expired_release_decision.head_sha.slice(0, 8)} and evidence {pr.expired_release_decision.evidence_hash.slice(0, 8)}.</p></div>
        </InlineNotice>
      )}
      {pr.release_decision && (
        <section className="release-owner-record">
          {pr.release_decision.decision === 'ready' ? <CheckCheck aria-hidden="true" /> : <Pause aria-hidden="true" />}
          <div><span>Local decision by {pr.release_decision.reviewer}</span><strong>{pr.release_decision.decision === 'ready' ? 'Readiness confirmed' : 'Release paused'}</strong><p>{pr.release_decision.note || 'No reviewer note was supplied.'}</p><time>{formatDate(pr.release_decision.created_at, true)} · {pr.release_decision.scope}</time></div>
        </section>
      )}

      <section className="release-detail-section">
        <SectionHeading title="External evidence" description="Repository and changed-diff matches, with observation times kept separate from publication dates." action={<span className="count-label">{plural(pr.external_evidence.length, 'match')}</span>} />
        {pr.external_evidence.length ? pr.external_evidence.map((evidence) => (
          <article className="release-external-card" key={evidence.id}>
            <div className="release-external-heading"><SeverityBadge severity={evidence.severity} /><span>{evidence.provider}</span><StateBadge state={evidence.state} /></div>
            <button className="release-external-title" onClick={() => onSelectSignal(evidence.id)}>{evidence.title}<ArrowUpRight aria-hidden="true" /></button>
            <p>{evidence.summary}</p>
            {evidence.matched_files.length > 0 && <div className="release-matched-files">{evidence.matched_files.map((path) => <code key={path}>{path}</code>)}</div>}
            {evidence.change && (
              <div className="web-diff-preview release-inline-diff">
                {evidence.change.removed.slice(0, 4).map((line, index) => <div className="web-diff-line removed" key={`r${index}`}><span>−</span><code>{line}</code></div>)}
                {evidence.change.added.slice(0, 6).map((line, index) => <div className="web-diff-line added" key={`a${index}`}><span>+</span><code>{line}</code></div>)}
              </div>
            )}
            {evidence.evidence.length > 0 && <CodeEvidence evidence={evidence.evidence.slice(0, 3)} />}
            <div className="receipt-stack">{evidence.source_receipts.slice(0, 2).map((receipt, index) => <SourceReceiptCard key={`${receipt.url}:${index}`} receipt={receipt} compact />)}</div>
          </article>
        )) : <div className="release-detail-empty"><Globe2 aria-hidden="true" /><p>No matching external evidence in the current bounded mapping. {pr.files_complete ? 'Changed file and dependency coverage is within the declared limit.' : 'File detail is incomplete; that absence is provisional.'}</p></div>}
      </section>

      <section className="release-detail-section">
        <SectionHeading title="Checks" description="GitHub check runs retrieved for this exact head; DriftCI does not execute repository code." action={<CheckState state={pr.check_summary.state} />} />
        {pr.checks.length ? <ul className="release-check-list">{pr.checks.map((check) => <li key={check.id}>
          {check.conclusion === 'success' ? <Check aria-hidden="true" /> : check.status === 'completed' ? <XCircle aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
          <span><strong>{check.name}</strong><small>{check.started_at ? formatDate(check.started_at, true) : 'Not started'}{check.completed_at ? ` → ${formatDate(check.completed_at, true)}` : ''}</small></span>
          {check.url ? <a href={check.url} target="_blank" rel="noreferrer noopener">{check.conclusion ?? label(check.status)}<ExternalLink aria-hidden="true" /></a> : <span>{check.conclusion ?? label(check.status)}</span>}
        </li>)}</ul> : <div className="release-detail-empty"><CircleDot aria-hidden="true" /><p>No checks were reported for this head{!pr.checks_complete ? ' in the bounded retrieval' : ''}. This is not a passing test result.</p></div>}
      </section>

      <section className="release-detail-section">
        <SectionHeading title="Changed files" description={`${pr.files.length} retrieved files, up to 30 per PR. Diffs retain 12,000 characters per file; omitted or truncated patches keep evidence incomplete.`} action={<FileDiff aria-hidden="true" />} />
        <div className="release-file-list">{pr.files.map((file) => <div key={file.path}><FileCode2 aria-hidden="true" /><code>{file.path}</code><span><b>+{file.additions}</b> <i>−{file.deletions}</i></span></div>)}</div>
        {!pr.detail_complete && <InlineNotice tone="warning"><RefreshCw aria-hidden="true" /><span>File, review or check detail is incomplete. {pr.detail_errors?.length ? `Retry pending for ${pr.detail_errors.join(', ')}.` : 'The declared coverage bound remains in effect until this PR changes.'}</span></InlineNotice>}
        <p className="release-mapping-note">Matching uses added and context lines from these diffs. Removed lines and deleted files do not count as current configuration.</p>
      </section>

      <section className="release-detail-section">
        <SectionHeading title="GitHub reviews" description="Remote review records are displayed independently from local release decisions." action={<UserCheck aria-hidden="true" />} />
        {reviews.length ? <ul className="release-review-list">{reviews.map((review) => <li key={review.id}><span className="review-avatar" aria-hidden="true">{review.reviewer.slice(0, 2).toUpperCase()}</span><div><strong>{review.reviewer}</strong><span>{label(review.state)} · {review.submitted_at ? formatDate(review.submitted_at, true) : 'No submission timestamp'}</span><code>{(review.commit_sha ?? '').slice(0, 10) || 'Head not supplied'}</code></div></li>)}</ul> : <div className="release-detail-empty"><UserCheck aria-hidden="true" /><p>No GitHub approvals were returned in the bounded review retrieval.</p></div>}
      </section>

      <div className="release-export-bar"><div><FileDiff aria-hidden="true" /><span><strong>Portable release evidence</strong><small>Head, checks, source snapshots, decision owner and scope limitations.</small></span></div><Button icon={Download} loading={exporting} onClick={() => void exportDecision()}>Export decision</Button></div>
    </Drawer>
  );
}

export function ReleaseRoom({ data, health, connected, busy, onRefresh, onSelectPr, onSelectSignal, onNavigate, onConnect }: {
  data: Bootstrap;
  health: Health | null;
  connected: boolean;
  busy: boolean;
  onRefresh: () => void;
  onSelectPr: (id: string) => void;
  onSelectSignal: (id: string) => void;
  onNavigate: (view: View) => void;
  onConnect: () => void;
}) {
  const release = data.release;
  const stream = health?.release_stream ?? release.status;
  const github = data.sources.find((source) => source.id === 'src-github-releases');
  const open = release.pull_requests.filter((pr) => pr.state === 'open');
  const repositoryUrl = `https://github.com/${data.workspace.repository}`;
  return (
    <div className="page release-page">
      <PageHeading
        eyebrow="Live release room · GitHub + Context.dev"
        title="The world can change after review."
        description="Pull requests, CI and official web evidence share one timeline. Every local decision identifies the commit and external evidence it covered."
        actions={<>
          <a className="button button-secondary" href={repositoryUrl} target="_blank" rel="noreferrer noopener"><GitBranch aria-hidden="true" /><span>Open repository</span></a>
          <Button variant="primary" icon={RefreshCw} loading={busy} onClick={onRefresh}>Refresh releases</Button>
        </>}
      />

      <section className="release-live-banner" aria-label="Live release stream status">
        <div className="release-stream-presence"><span className={cx('release-presence-dot', connected ? 'connected' : 'disconnected')} /><div><strong>{connected ? 'Event stream connected' : 'Event stream reconnecting'}</strong><span>{stream.webhook_configured ? 'Verified webhooks + conditional polling' : `GitHub conditional polling every ${stream.poll_interval_seconds}s`}</span></div></div>
        <div><span>Open in recent window</span><strong>{release.counts.open}</strong></div>
        <div><span>Needs review</span><strong>{release.counts.needs_review}</strong></div>
        <div><span>Evidence confirmed</span><strong>{release.counts.ready}</strong></div>
        <div className="release-source-cadence"><span>Context.dev status watches</span><strong>{stream.status_hot_ttl_seconds ?? 45}s when release activity is hot · {stream.status_cache_ttl_seconds ?? 300}s otherwise</strong></div>
      </section>

      {(github?.error || stream.last_error) && <InlineNotice tone="warning" className="release-source-warning"><Radio aria-hidden="true" /><div><strong>GitHub release source needs attention. Retained evidence stays visible.</strong><p>{github?.error || stream.last_error}</p></div></InlineNotice>}
      {!!stream.detail_pending && <InlineNotice tone="info" className="release-source-warning"><RefreshCw aria-hidden="true" /><span>{plural(stream.detail_pending, 'pull request')} awaits its bounded detail turn. Refresh again or let the next poll complete it.</span></InlineNotice>}

      <div className="release-workspace-grid">
        <section className="release-queue-section">
          <SectionHeading title="Release queue" description="Recent open pull requests first. GitHub reviews and local DriftCI decisions stay distinct." action={<span className="count-label">{plural(open.length, 'open PR')}</span>} />
          {release.pull_requests.length ? <div className="release-card-list">{release.pull_requests.map((pr) => <ReleaseCard key={pr.id} pr={pr} onOpen={onSelectPr} onSelectSignal={onSelectSignal} />)}</div> : (
            <div className="panel release-empty-panel"><EmptyState
              icon={GitPullRequestArrow}
              title={data.workspace.source === 'github' ? 'No pull requests in the recent window' : 'Connect your release workflow'}
              description={data.workspace.source === 'github' ? 'DriftCI checks the recent PR window independently of full web scans. Open a pull request or refresh when one exists.' : 'Connect a public GitHub repository to inspect real PRs, CI checks and external model/dependency evidence.'}
              action={data.workspace.source === 'github' ? <Button icon={RefreshCw} loading={busy} onClick={onRefresh}>Check recent pull requests</Button> : <Button variant="primary" icon={GitBranch} onClick={onConnect}>Connect a GitHub repository</Button>}
            /></div>
          )}
          <div className="release-queue-note"><GitCommitHorizontal aria-hidden="true" /><span>Recent window: up to 10 pull requests, with bounded file, review and check retrieval. Initial imports are baselines.</span></div>
        </section>
        <ActivityFeed events={release.events} onSelectSignal={onSelectSignal} onOpenPr={onSelectPr} onNavigate={onNavigate} />
      </div>

      <section className="release-explainer">
        <div><Clock3 aria-hidden="true" /><span><strong>What made this approval stale?</strong><p>Compare the external observation with the GitHub review time, then inspect the exact source diff.</p></span></div>
        <div><ShieldCheck aria-hidden="true" /><span><strong>Who accepted this evidence?</strong><p>A named reviewer records a local decision for one head and one evidence hash.</p></span></div>
        <Button variant="ghost" onClick={() => onNavigate('overview')}>Workspace overview<ArrowRight aria-hidden="true" /></Button>
      </section>
    </div>
  );
}
