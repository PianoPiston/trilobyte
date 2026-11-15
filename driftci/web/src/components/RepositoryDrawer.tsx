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
import { errorText, label, relativeTime } from '../utils';
import { Button, Drawer, InlineNotice } from './ui';

function validGithubUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:'
      && (url.hostname === 'github.com' || url.hostname === 'www.github.com')
      && url.pathname.split('/').filter(Boolean).length >= 2;
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
          <div><dt><Server aria-hidden="true" />Environment</dt><dd>{data.workspace.environment}</dd></div>
          <div><dt><Globe2 aria-hidden="true" />Last scan</dt><dd>{relativeTime(health?.last_scan_at ?? null)}</dd></div>
          <div><dt><Github aria-hidden="true" />GitHub</dt><dd>{health?.github.mode ?? 'Status unavailable'}</dd></div>
        </dl>
      </section>

      <section className="drawer-section repository-connect">
        <div className="drawer-section-heading"><h3>Connect a public repository</h3><Github aria-hidden="true" /></div>
        <p>DriftCI downloads and scans the repository through the backend. Local paths and command execution are not accepted.</p>
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
          <small id="repository-help">Public GitHub repositories over HTTPS.</small>
          {error && <InlineNotice tone="error" role="alert">{error}</InlineNotice>}
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
