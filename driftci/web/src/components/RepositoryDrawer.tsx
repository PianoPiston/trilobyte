import {
  ArchiveRestore,
  ArrowUpRight,
  Braces,
  CheckCircle2,
  FlaskConical,
  GitBranch,
  Github,
  Globe2,
  History,
  Link2,
  RotateCcw,
  Server,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { Bootstrap, Health } from '../types';
import { errorText, label, plural, relativeTime } from '../utils';
import { Button, Drawer, InlineNotice } from './ui';

function formatBytes(value: number) {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)} MB` : `${Math.round(value / 1000)} KB`;
}

function validGithubUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:'
      && url.hostname === 'github.com'
      && url.pathname.split('/').filter(Boolean).length === 2
      && !url.username && !url.password && !url.search && !url.hash;
  } catch {
    return false;
  }
}

export function RepositoryDrawer({ data, health, busy, onClose, onConnect, onReplay, onResetReplay, onRestore }: {
  data: Bootstrap;
  health: Health | null;
  busy: string;
  onClose: () => void;
  onConnect: (url: string) => Promise<void>;
  onReplay: () => void;
  onResetReplay: () => Promise<void>;
  onRestore: () => Promise<void>;
}) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState<'reset' | 'restore' | null>(null);

  const connect = async (event: FormEvent) => {
    event.preventDefault();
    const normalized = url.trim();
    if (!validGithubUrl(normalized)) {
      setError('Enter an HTTPS GitHub repository URL, such as https://github.com/owner/repository.');
      return;
    }
    setError('');
    try {
      await onConnect(normalized);
      setUrl('');
    } catch (requestError) {
      setError(errorText(requestError));
    }
  };

  const runConfirmed = async () => {
    const action = confirm;
    setConfirm(null);
    if (action === 'reset') await onResetReplay();
    if (action === 'restore') await onRestore();
  };

  const coverage = data.workspace.coverage;
  const osv = data.sources.find((source) => source.id === 'src-osv');
  const native = Array.from(new Map(data.dependencies.filter((dependency) => dependency.ecosystem === 'Native').map((dependency) => [dependency.name, dependency])).values());

  return (
    <Drawer title="Repository & demo controls" subtitle="Connection, provenance and reproducible examples" onClose={onClose}>
      <section className="workspace-card">
        <div className="workspace-card-icon"><Braces aria-hidden="true" /></div>
        <div className="workspace-card-heading">
          <span>Current workspace</span>
          <h3>{data.workspace.name}</h3>
          <code>{data.workspace.repository}</code>
        </div>
        <span className={`badge ${data.workspace.source === 'demo' ? 'mode-demo' : 'mode-live'}`}>
          {data.workspace.source === 'demo' ? <FlaskConical aria-hidden="true" /> : <Github aria-hidden="true" />}
          {data.workspace.source === 'demo' ? 'Controlled demo' : label(data.workspace.source)}
        </span>
        <dl>
          <div><dt><GitBranch aria-hidden="true" />Branch</dt><dd><code>{data.workspace.branch}</code></dd></div>
          <div><dt><Server aria-hidden="true" />Scope</dt><dd>{data.workspace.environment}</dd></div>
          <div><dt><Globe2 aria-hidden="true" />Last scan</dt><dd>{relativeTime(health?.last_scan_at ?? null)}</dd></div>
          <div><dt><Github aria-hidden="true" />GitHub</dt><dd>{health?.github.mode ?? 'Status unavailable'}</dd></div>
        </dl>
        {coverage && (
          <div className={`repository-coverage ${coverage.complete ? '' : 'is-partial'}`} data-testid="repository-coverage">
            <div className="coverage-heading"><strong>Repository intelligence coverage</strong><span>{coverage.source_complete ? 'Wider source index complete' : 'Targeted, with explicit gaps'}</span></div>
            <p><b>{coverage.files_read.toLocaleString()} text files</b> · {formatBytes(coverage.bytes_read)} · commit <code>{coverage.commit_sha?.slice(0, 12) ?? 'unavailable'}</code>{coverage.source_read_seconds !== undefined && <> · {coverage.source_read_seconds.toFixed(1)}s file-read time</>}.</p>
            <dl className="coverage-facts">
              <div><dt>Dependency manifests</dt><dd>{coverage.manifest_files_read ?? 0} / {coverage.manifest_candidates ?? 0} discovered read</dd></div>
              <div><dt>GitHub dependency graph</dt><dd>{coverage.structured_packages ?? 0} package records</dd></div>
              <div><dt>Native-version files</dt><dd>{coverage.native_version_files_read ?? 0} read</dd></div>
              <div><dt>Wider source index</dt><dd>{coverage.source_complete ? 'Complete for selected tree' : `${coverage.skipped_budget_files.toLocaleString()} budget-skipped files`}</dd></div>
            </dl>
            <small>No archive or clone. GitHub listed {coverage.repository_files.toLocaleString()} tree entries{coverage.tree_truncated ? ' (truncated)' : ''}. API metadata uses {coverage.metadata_transport === 'context.dev_bytes' ? 'Context.dev’s byte-preserving request transport' : 'direct GitHub requests'}; code reads use commit-pinned raw URLs.</small>
            {coverage.context_metadata_error && <small className="coverage-warning">A Context.dev metadata request fell back to direct GitHub: {coverage.context_metadata_error}</small>}
            {osv && (
              <div className="advisory-coverage">
                <div><strong>Registry advisories</strong><span>{osv.packages_checked?.toLocaleString() ?? 0} / {osv.packages_eligible?.toLocaleString() ?? 0} exact versions checked</span></div>
                <p>{osv.advisory_details_retrieved ?? 0} full advisory details retrieved; {osv.advisory_details_pending ?? 0} pending. {plural(osv.packages_unsupported ?? 0, 'native, project or unsupported comparison')} excluded. {plural(osv.packages_unresolved ?? 0, 'remaining unresolved declaration')} retained for review.</p>
              </div>
            )}
            <div className="coverage-limit-grid">
              <span><b>{coverage.dependency_parse_errors?.length ?? 0}</b> manifest parse failures</span>
              <span><b>{coverage.skipped_large_files}</b> oversized manifest/native files</span>
              <span><b>{coverage.failed_files + coverage.timed_out_files}</b> failed/timed-out reads</span>
              <span><b>{coverage.manifests_missing ?? 0}</b> discovered manifests not read</span>
            </div>
            {!!coverage.dependency_parse_errors?.length && <details className="parse-error-list"><summary>Review manifest parsing evidence</summary>{coverage.dependency_parse_errors.map((item) => <div key={item.path}><code>{item.path}</code><span>{item.reason}</span></div>)}</details>}
            {!!native.length && <details className="native-component-list"><summary>Native declaration inventory</summary><p>Versions come from native headers and dependency files. Platform-specific advisory review is required for these declarations.</p>{native.map((dependency) => <div key={dependency.name}><strong>{dependency.name}</strong><code>{dependency.version}</code><small title={dependency.manifest}>{dependency.manifest}</small></div>)}</details>}
            {!coverage.source_complete && <small className="coverage-warning">Wider source reading is partial; this section reports source reads, manifest parsing and advisory eligibility separately. Partial source coverage is not evidence of absence.</small>}
          </div>
        )}
      </section>

      <section className="drawer-section repository-connect">
        <div className="drawer-section-heading"><h3>Connect a public repository</h3><Github aria-hidden="true" /></div>
        <p>DriftCI reads GitHub metadata, the dependency graph, native declarations, manifests and targeted source files at an immutable commit. It never downloads repository archives, clones, installs or executes code.</p>
        <form onSubmit={(event) => void connect(event)} noValidate>
          <label htmlFor="repository-url">GitHub repository URL</label>
          <div className="repository-input">
            <Link2 aria-hidden="true" />
            <input
              id="repository-url"
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://github.com/owner/repository"
              autoComplete="url"
              aria-describedby="repository-help"
            />
          </div>
          <small id="repository-help">Public GitHub repositories over HTTPS, including large repositories such as nodejs/node. Repository archives and clones are never downloaded. Manifest completeness and source coverage are reported independently.</small>
          {error && <InlineNotice tone="error" role="alert">{error}</InlineNotice>}
          {busy === 'connect' && <InlineNotice className="repository-progress" role="status"><div><strong>Reading manifests and source evidence…</strong><p>GitHub metadata and targeted reads run first, followed by exact-version OSV checks and full advisory-detail retrieval. File and time limits are reported above; unsupported comparisons remain review items.</p></div></InlineNotice>}
          <Button type="submit" variant="primary" icon={ArrowUpRight} loading={busy === 'connect'}>Connect & scan repository</Button>
        </form>
      </section>

      <section className="drawer-section demo-controls">
        <div className="drawer-section-heading"><h3>Historical incident</h3><History aria-hidden="true" /></div>
        <div className="demo-explanation">
          <span className="badge mode-replay">Historical replay</span>
          <h4>OpenAI gpt-4-0314 retirement</h4>
          <p>Replays the documented shutdown on 26 March 2026. This is a historical example, not a newly announced event.</p>
        </div>
        <div className="demo-control-buttons">
          <Button icon={History} loading={busy === 'replay'} onClick={onReplay}>Replay 2026 incident</Button>
          <Button icon={RotateCcw} loading={busy === 'reset'} onClick={() => setConfirm('reset')}>Reset replay</Button>
        </div>
        {confirm === 'reset' && (
          <InlineNotice tone="warning" className="confirm-inline">
            <p>Reset the historical replay and restore its pre-replay workspace state?</p>
            <div><Button size="small" onClick={() => setConfirm(null)}>Cancel</Button><Button size="small" variant="primary" onClick={() => void runConfirmed()}>Reset replay</Button></div>
          </InlineNotice>
        )}
      </section>

      <section className="drawer-section restore-section">
        <div className="drawer-section-heading"><h3>Example workspace</h3><ArchiveRestore aria-hidden="true" /></div>
        <p>Restore the built-in <code>junction/orders-ai</code> workspace and its seeded evidence.</p>
        <Button icon={ArchiveRestore} loading={busy === 'restore'} onClick={() => setConfirm('restore')}>Restore example workspace</Button>
        {confirm === 'restore' && (
          <InlineNotice tone="warning" className="confirm-inline">
            <p>Replace the current workspace with the built-in example? Repository-connected workspace data will no longer be shown.</p>
            <div><Button size="small" onClick={() => setConfirm(null)}>Cancel</Button><Button size="small" variant="danger" onClick={() => void runConfirmed()}>Restore example</Button></div>
          </InlineNotice>
        )}
        {data.workspace.source === 'demo' && <span className="workspace-example-note"><CheckCircle2 aria-hidden="true" />The example workspace is active.</span>}
      </section>
    </Drawer>
  );
}
