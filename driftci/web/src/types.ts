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
}

export interface SourceReceipt {
  publisher: string;
  title: string;
  url: string;
  retrieved_at: string;
  mode: string;
  quote: string;
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
  recommendation: string;
  evidence: CodeEvidence[];
  source_receipts: SourceReceipt[];
  remediation_id: string | null;
  created_at: string;
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

export interface Bootstrap {
  workspace: Workspace;
  summary: Summary;
  signals: Signal[];
  dependencies: Dependency[];
  activity: Activity[];
  sources: WatchedSource[];
  incidents: Incident[];
  history: Incident[];
  remediations?: Remediation[];
  metrics: {
    source_receipts: number;
    files_indexed: number;
    dependencies_indexed: number;
    context_queries: number;
  };
}

export interface Health {
  ok: boolean;
  version: string;
  context_dev: { configured: boolean; mode: string };
  github: { configured: boolean; mode: string };
  last_scan_at: string | null;
  source_counts: Record<string, number>;
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

export type View = 'overview' | 'radar' | 'vulnerabilities' | 'evidence';
