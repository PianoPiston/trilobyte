export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type SignalKind = 'deprecation' | 'vulnerability' | 'api' | 'pricing' | 'status';
export type SignalState = 'needs_action' | 'acknowledged' | 'fix_ready' | 'resolved' | 'monitoring';
export type ActionStatus = 'done' | 'pending';

export interface RepositoryCoverage {
  mode: 'github_tree_selective';
  archive_downloaded: false;
  commit_sha: string;
  complete: boolean;
  tree_truncated: boolean;
  repository_files: number;
  candidate_files: number;
  selected_files: number;
  files_read: number;
  skipped_large_files: number;
  skipped_budget_files: number;
  failed_files: number;
  timed_out_files: number;
  source_read_seconds?: number;
  time_budget_seconds?: number;
  per_file_timeout_seconds?: number;
  bytes_read: number;
  file_limit: number;
  byte_limit: number;
  per_file_limit: number;
  repository_size_kb: number | null;
}

export interface Workspace {
  id: string;
  name: string;
  repository: string;
  branch: string;
  environment: string;
  source: string;
  coverage?: RepositoryCoverage;
}

export interface Summary {
  risk_score: number;
  active_changes: number;
  critical_vulnerabilities: number;
  affected_dependencies: number;
  remediations_ready: number;
  production_models: number;
  resolved_this_month: number;
  mean_response_hours: number;
  watched_sources: number;
  observed_changes: number;
  open_prs: number;
  release_reviews: number;
  live_release_events: number;
}

export interface SourceReceipt {
  publisher: string;
  title: string;
  url: string;
  retrieved_at: string;
  mode: string;
  quote: string;
}

export interface WebObservation {
  id: string;
  source_id: string;
  title: string;
  url: string;
  observed_at: string;
  mode: string;
  content_hash: string;
  previous_hash: string;
  added_lines: number;
  removed_lines: number;
  added: string[];
  removed: string[];
  publisher?: string;
  source_title?: string;
  signal_id?: string | null;
  matched_terms?: string[];
}

export interface Discovery {
  id: string;
  title: string;
  url: string;
  summary: string;
  published_at: string | null;
  retrieved_at: string;
  mode: string;
  matched_terms: string[];
}

export interface CodeEvidence {
  file: string;
  line: number;
  snippet: string;
  reason: string;
}

export interface Signal {
  id: string;
  kind: SignalKind;
  severity: Severity;
  state: SignalState;
  title: string;
  summary: string;
  provider: string;
  affected_assets: string[];
  deadline: string | null;
  cve: string | null;
  cvss: number | null;
  kev: boolean;
  fixed_version: string | null;
  replacement: string | null;
  reachability: string | null;
  reachability_reason?: string | null;
  recommendation: string;
  evidence: CodeEvidence[];
  source_receipts: SourceReceipt[];
  remediation_id: string | null;
  created_at: string;
  watch_id?: string;
  change?: WebObservation;
  reviewed_at?: string | null;
  observed_at?: string | null;
}

export interface Dependency {
  name: string;
  ecosystem: string;
  version: string;
  kind: string;
  health: string;
  usage_count: number;
  issues: number;
}

export interface Activity {
  id: string;
  type: string;
  title: string;
  detail: string;
  created_at: string;
}

export interface WatchedSource {
  id: string;
  publisher: string;
  title: string;
  url: string;
  status: string;
  last_checked_at: string;
  event_count: number;
  error?: string | null;
  packages_total?: number;
  packages_checked?: number;
  packages_pending?: number;
  category?: string;
  package?: string | null;
  custom?: boolean;
  watch?: boolean;
  baseline_at?: string;
  last_changed_at?: string;
  observations?: WebObservation[];
}

export interface IncidentAction {
  id: string;
  label: string;
  detail: string;
  status: ActionStatus;
  completed_at: string | null;
}

export interface Incident {
  id: string;
  cve: string;
  title: string;
  severity: Severity;
  cvss: number | null;
  kev: boolean;
  state: string;
  first_seen_at: string;
  resolved_at: string | null;
  affected_package: string;
  affected_version: string;
  fixed_version: string | null;
  reachability: string;
  reachability_reason: string;
  summary: string;
  affected_files: CodeEvidence[];
  source_receipts: SourceReceipt[];
  actions: IncidentAction[];
  signal_id: string | null;
}

export interface ReleaseEvidence {
  id: string;
  kind: SignalKind;
  severity: Severity;
  state: SignalState;
  title: string;
  summary: string;
  provider: string;
  created_at: string;
  observed_at: string | null;
  matched_files: string[];
  evidence: CodeEvidence[];
  source_receipts: SourceReceipt[];
  change: WebObservation | null;
}

export interface ReleaseDecision {
  id: string;
  pr_id: string;
  head_sha: string;
  evidence_hash: string;
  decision: 'ready' | 'hold';
  reviewer: string;
  note: string;
  created_at: string;
  scope: string;
}

export interface PullRequest {
  id: string;
  number: number;
  state: 'open' | 'closed';
  title: string;
  repository: string;
  url: string;
  author: string;
  draft: boolean;
  head_sha: string;
  head_ref: string;
  base_ref: string;
  created_at: string;
  updated_at: string;
  merged_at: string | null;
  merged: boolean;
  changed_files: number;
  files: Array<{ path: string; status: string; additions: number; deletions: number; changes: number; patch_complete?: boolean }>;
  files_complete: boolean;
  detail_errors?: string[];
  reviews_complete: boolean;
  checks_complete: boolean;
  detail_complete: boolean;
  reviews: Array<{ id: string; state: string; reviewer: string; submitted_at: string | null; commit_sha: string | null; url: string | null }>;
  checks: Array<{ id: string; name: string; status: string; conclusion: string | null; started_at: string | null; completed_at: string | null; url: string | null }>;
  check_summary: { state: string; total: number; pending: number; failed: number; passed: number };
  external_evidence: ReleaseEvidence[];
  active_external_count: number;
  latest_external_observation: string | null;
  latest_remote_approval: string | null;
  current_head_approval: string | null;
  outdated_remote_review: boolean;
  evidence_hash: string;
  release_decision: ReleaseDecision | null;
  expired_release_decision: ReleaseDecision | null;
  readiness: string;
}

export interface ReleaseEvent {
  seq: number;
  kind: string;
  title: string;
  detail: string;
  occurred_at: string;
  received_at: string;
  pr_id: string | null;
  pr_number: number | null;
  url: string | null;
  head_sha: string | null;
  source: string;
  mode: string;
  baseline: boolean;
  affected_pr_numbers?: number[];
  signal_id?: string;
  decision?: 'ready' | 'hold';
}

export interface ReleaseStreamStatus {
  enabled?: boolean;
  implementation: string;
  poll_interval_seconds: number;
  webhook_configured: boolean;
  last_polled_at?: string;
  last_success_at?: string;
  last_transport_mode?: string;
  last_error?: string | null;
  detail_pending?: number;
  release_requests?: number;
  rate_limit_remaining?: number;
  sse_path?: string;
  webhook_path?: string | null;
  status_cache_ttl_seconds?: number;
  status_hot_ttl_seconds?: number;
}

export interface ReleaseData {
  pull_requests: PullRequest[];
  events: ReleaseEvent[];
  latest_seq: number;
  status: ReleaseStreamStatus;
  counts: { open: number; needs_review: number; ready: number; live_events: number };
}

export interface Bootstrap {
  workspace: Workspace;
  summary: Summary;
  signals: Signal[];
  dependencies: Dependency[];
  activity: Activity[];
  sources: WatchedSource[];
  incidents: Incident[];
  history: Incident[];
  release: ReleaseData;
  remediations?: Remediation[];
  changes: WebObservation[];
  discoveries: Discovery[];
  research: { query?: string; retrieved_at?: string; mode?: string } | null;
  metrics: {
    source_receipts: number;
    files_indexed: number;
    dependencies_indexed: number;
    context_queries: number;
    context_credits: number;
  };
}

export interface Health {
  ok: boolean;
  version: string;
  context_dev: {
    configured: boolean;
    mode: string;
    usage: {
      queries: number;
      credits: number;
      daily_queries: number;
      daily_credits: number;
      daily_credit_limit: number;
      cache_ttl_seconds: number;
    };
  };
  github: { configured: boolean; mode: string };
  last_scan_at: string | null;
  source_counts: Record<string, number>;
  watcher?: { enabled: boolean; interval_seconds: number; implementation: string };
  release_stream?: ReleaseStreamStatus;
}

export interface IncidentsResponse {
  active: Incident[];
  history: Incident[];
  metrics: {
    active: number;
    critical: number;
    resolved: number;
    mean_response_hours: number;
  };
}

export interface RemediationFile {
  path: string;
  before: string;
  after: string;
  diff: string;
  additions: number;
  deletions: number;
}

export interface RemediationCheck {
  name: string;
  status: string;
  detail: string;
}

export interface Remediation {
  id: string;
  signal_id: string;
  title: string;
  status: string;
  summary: string;
  files: RemediationFile[];
  checks: RemediationCheck[];
  source_receipts: SourceReceipt[];
  can_open_pr: boolean;
  created_at: string;
  approved_at: string | null;
  pr_url: string | null;
  pr_number: number | null;
}

export type View = 'release' | 'overview' | 'watch' | 'radar' | 'vulnerabilities' | 'evidence';
