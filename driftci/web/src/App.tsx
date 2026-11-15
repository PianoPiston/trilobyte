import {
  Activity,
  BellRing,
  Boxes,
  ChevronDown,
  FlaskConical,
  Github,
  Globe2,
  History,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  Radar,
  ReceiptText,
  RefreshCw,
  ScanSearch,
  Settings2,
  ShieldAlert,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import type {
  Bootstrap,
  Health,
  Incident,
  Signal,
  View,
} from './types';
import { cx, errorText, relativeTime } from './utils';
import { ChangeRadar } from './pages/ChangeRadar';
import { Evidence } from './pages/Evidence';
import { MissionControl } from './pages/MissionControl';
import { Vulnerabilities } from './pages/Vulnerabilities';
import { WebWatch } from './pages/WebWatch';
import { RepositoryDrawer } from './components/RepositoryDrawer';
import { SignalDrawer } from './components/SignalDrawer';
import {
  Button,
  ErrorState,
  IconButton,
  InlineNotice,
  Modal,
  ModeBadge,
  Spinner,
  Toast,
  type ToastData,
} from './components/ui';

const navigation: Array<{ id: View; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'overview', label: 'Mission Control', icon: LayoutDashboard },
  { id: 'watch', label: 'Web Watch', icon: Globe2 },
  { id: 'radar', label: 'Change Inbox', icon: Radar },
  { id: 'vulnerabilities', label: 'Vulnerabilities', icon: ShieldAlert },
  { id: 'evidence', label: 'Evidence', icon: ReceiptText },
];

function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true"><Activity /></span>
      <span className="brand-word">Drift<span>CI</span></span>
    </span>
  );
}

export default function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [initialError, setInitialError] = useState('');
  const [refreshError, setRefreshError] = useState('');
  const [busy, setBusy] = useState('');
  const [view, setView] = useState<View>('overview');
  const [mobileNavigation, setMobileNavigation] = useState(false);
  const [repositoryOpen, setRepositoryOpen] = useState(false);
  const [selectedSignalId, setSelectedSignalId] = useState('');
  const [replayConfirmation, setReplayConfirmation] = useState(false);
  const [toast, setToast] = useState<ToastData | null>(null);

  const notify = useCallback((message: string, tone: 'success' | 'error' | 'info' = 'info') => {
    setToast({ id: Date.now(), message, tone });
  }, []);
  const dismissToast = useCallback(() => setToast(null), []);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
    } catch {
      // Workspace evidence remains usable when the secondary health request fails.
    }
  }, []);

  const loadInitial = useCallback(async () => {
    setInitialLoading(true);
    setInitialError('');
    try {
      const [bootstrapResult, healthResult] = await Promise.allSettled([api.bootstrap(), api.health()]);
      if (bootstrapResult.status === 'rejected') throw bootstrapResult.reason;
      setData(bootstrapResult.value);
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    } catch (requestError) {
      setInitialError(errorText(requestError));
    } finally {
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => { void loadInitial(); }, [loadInitial]);

  const navigate = (nextView: View) => {
    setView(nextView);
    setMobileNavigation(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const runWorkspaceAction = useCallback(async (
    key: string,
    action: () => Promise<Bootstrap>,
    successMessage: string,
  ) => {
    setBusy(key);
    setRefreshError('');
    try {
      const result = await action();
      setData(result);
      setSelectedSignalId('');
      notify(successMessage, 'success');
      void refreshHealth();
    } catch (requestError) {
      const message = errorText(requestError);
      setRefreshError(message);
      notify(message, 'error');
    } finally {
      setBusy('');
    }
  }, [notify, refreshHealth]);

  const connectRepository = async (url: string) => {
    setBusy('connect');
    setRefreshError('');
    try {
      const result = await api.connectRepository(url);
      setData(result);
      setRepositoryOpen(false);
      setSelectedSignalId('');
      notify(`Connected ${result.workspace.repository} on ${result.workspace.branch}.`, 'success');
      void refreshHealth();
    } catch (requestError) {
      setRefreshError(errorText(requestError));
      throw requestError;
    } finally {
      setBusy('');
    }
  };

  const updateSignal = (updated: Signal) => {
    setData((current) => current ? {
      ...current,
      signals: current.signals.map((signal) => signal.id === updated.id ? updated : signal),
    } : current);
  };

  const updateIncident = (updated: Incident) => {
    setData((current) => current ? {
      ...current,
      incidents: updated.state === 'resolved'
        ? current.incidents.filter((incident) => incident.id !== updated.id)
        : [...current.incidents.filter((incident) => incident.id !== updated.id), updated],
      history: updated.state === 'resolved'
        ? [...current.history.filter((incident) => incident.id !== updated.id), updated]
        : current.history.filter((incident) => incident.id !== updated.id),
    } : current);
    // Incident transitions also change signal state and aggregate metrics.
    void api.bootstrap().then((result) => {
      setData(result);
    }).catch(() => { /* The incident response already updated successfully. */ });
  };

  const addWatch = async (url: string, title: string) => {
    setBusy('add-watch');
    try {
      const result = await api.addWatch(url, title);
      setData(result);
      notify('Web watch added. A baseline is established on first retrieval.', 'success');
      void refreshHealth();
    } catch (requestError) {
      notify(errorText(requestError), 'error');
      throw requestError;
    } finally {
      setBusy('');
    }
  };

  const removeWatch = async (key: string) => {
    setBusy('remove-watch');
    try {
      setData(await api.removeWatch(key));
      notify('Custom web watch removed.', 'success');
    } catch (requestError) {
      notify(errorText(requestError), 'error');
      throw requestError;
    } finally {
      setBusy('');
    }
  };

  if (initialLoading) {
    return (
      <main className="startup-screen">
        <div className="startup-brand"><Brand /><span className="environment-badge">Operations console</span></div>
        <div className="startup-loader"><Spinner label="Loading workspace, evidence and source status" /></div>
        <div className="startup-skeleton" aria-hidden="true"><div /><div /><div /><div /></div>
      </main>
    );
  }

  if (initialError || !data) {
    return (
      <main className="startup-screen startup-error">
        <div className="startup-brand"><Brand /><span className="environment-badge">Login-free demo</span></div>
        <ErrorState
          fullScreen
          title="The operations console is offline"
          message={initialError || 'The bootstrap response did not include workspace data.'}
          onRetry={() => void loadInitial()}
        />
        <p className="startup-help">The Vite development server proxies <code>/api</code> to <code>127.0.0.1:8100</code>. Start the backend, then retry.</p>
      </main>
    );
  }

  const selectedInitialSignal = data.signals.find((signal) => signal.id === selectedSignalId);

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      {mobileNavigation && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileNavigation(false)} />}
      <aside className={cx('sidebar', mobileNavigation && 'sidebar-open')}>
        <div className="sidebar-top">
          <button className="brand-button" onClick={() => navigate('overview')} aria-label="DriftCI mission control"><Brand /></button>
          <IconButton className="mobile-sidebar-close" icon={PanelLeftClose} label="Close navigation" onClick={() => setMobileNavigation(false)} />
        </div>

        <button className="sidebar-workspace" onClick={() => setRepositoryOpen(true)}>
          <span className="workspace-avatar"><Boxes aria-hidden="true" /></span>
          <span><strong>{data.workspace.name}</strong><small>{data.workspace.repository}</small></span>
          <ChevronDown aria-hidden="true" />
        </button>

        <div className="sidebar-workspace-mode">
          {data.workspace.source === 'demo' ? <FlaskConical aria-hidden="true" /> : <Github aria-hidden="true" />}
          {data.workspace.source === 'demo' ? 'Controlled demo workspace' : 'Connected repository'}
        </div>

        <nav className="main-navigation" aria-label="Main navigation">
          <span className="navigation-label">Operations</span>
          {navigation.map((item) => {
            const Icon = item.icon;
            const count = item.id === 'watch' ? data.summary.observed_changes
              : item.id === 'radar' ? data.summary.active_changes
              : item.id === 'vulnerabilities' ? data.incidents.length
                : item.id === 'evidence' ? data.metrics.source_receipts : null;
            return (
              <button key={item.id} className={cx(view === item.id && 'active')} onClick={() => navigate(item.id)} aria-current={view === item.id ? 'page' : undefined}>
                <Icon aria-hidden="true" /><span>{item.label}</span>{count !== null && <small>{count}</small>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <button className="sidebar-demo-card" onClick={() => setReplayConfirmation(true)}>
            <History aria-hidden="true" />
            <span><strong>Historical replay</strong><small>OpenAI retirement · 26 Mar 2026</small></span>
          </button>
          <div className="sidebar-status">
            <span className={cx('status-dot', health?.ok ? 'dot-live' : 'dot-cached')} />
            <span>{health?.ok ? 'API connected' : 'Health status unavailable'}</span>
            {health?.version && <code>v{health.version}</code>}
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="command-bar">
          <div className="command-left">
            <IconButton className="mobile-menu" icon={Menu} label="Open navigation" onClick={() => setMobileNavigation(true)} />
            <button className="mobile-brand" onClick={() => navigate('overview')} aria-label="DriftCI mission control"><Brand /></button>
            <div className="source-mode-summary">
              {health && <ModeBadge mode={health.context_dev.configured ? health.context_dev.mode : 'not_configured'} />}
              {!health && <ModeBadge mode="health_unavailable" />}
            </div>
          </div>
          <div className="command-actions">
            <span className="last-scan">Last scan <strong>{relativeTime(health?.last_scan_at ?? null)}</strong></span>
            <IconButton icon={Settings2} label="Repository and demo controls" onClick={() => setRepositoryOpen(true)} />
            <Button
              variant="primary"
              icon={ScanSearch}
              loading={busy === 'scan'}
              onClick={() => void runWorkspaceAction('scan', api.scan, 'Live web and vulnerability intelligence refreshed.')}
            >Refresh web</Button>
          </div>
        </header>

        {refreshError && (
          <InlineNotice tone="error" className="stale-data-banner" role="alert">
            <BellRing aria-hidden="true" />
            <div><strong>Refresh failed. Showing the last successful workspace data.</strong><span>{refreshError}</span></div>
            <Button size="small" icon={RefreshCw} loading={busy === 'scan'} onClick={() => void runWorkspaceAction('scan', api.scan, 'Live web and vulnerability intelligence refreshed.')}>Retry refresh</Button>
            <IconButton icon={X} label="Dismiss refresh error" onClick={() => setRefreshError('')} />
          </InlineNotice>
        )}

        <main id="main-content" className="main-content" tabIndex={-1}>
          {view === 'overview' && <MissionControl data={data} health={health} onNavigate={navigate} onSelectSignal={setSelectedSignalId} />}
          {view === 'watch' && <WebWatch data={data} health={health} busy={busy} onAddWatch={addWatch} onRemoveWatch={removeWatch} onSelectSignal={setSelectedSignalId} />}
          {view === 'radar' && <ChangeRadar initialSignals={data.signals} onSelectSignal={setSelectedSignalId} />}
          {view === 'vulnerabilities' && <Vulnerabilities data={data} onIncidentUpdated={updateIncident} />}
          {view === 'evidence' && <Evidence data={data} onSelectSignal={setSelectedSignalId} onNavigate={navigate} />}
        </main>
      </div>

      {selectedSignalId && (
        <SignalDrawer
          signalId={selectedSignalId}
          initialSignal={selectedInitialSignal}
          onClose={() => setSelectedSignalId('')}
          onSignalUpdated={updateSignal}
        />
      )}

      {repositoryOpen && (
        <RepositoryDrawer
          data={data}
          health={health}
          busy={busy}
          onClose={() => setRepositoryOpen(false)}
          onConnect={connectRepository}
          onReplay={() => setReplayConfirmation(true)}
          onResetReplay={() => runWorkspaceAction('reset', api.resetReplay, 'Historical replay reset.')}
          onRestore={async () => {
            await runWorkspaceAction('restore', api.restoreWorkspace, 'Built-in example workspace restored.');
            setRepositoryOpen(false);
          }}
        />
      )}

      {replayConfirmation && (
        <Modal
          title="Replay a historical incident"
          subtitle="Controlled example · 26 March 2026"
          onClose={() => { if (busy !== 'replay') setReplayConfirmation(false); }}
          footer={
            <>
              <span className="modal-footer-note"><FlaskConical aria-hidden="true" />Reproducible demo evidence</span>
              <div className="dialog-footer-actions">
                <Button onClick={() => setReplayConfirmation(false)}>Cancel</Button>
                <Button
                  variant="primary"
                  icon={History}
                  loading={busy === 'replay'}
                  onClick={() => {
                    setReplayConfirmation(false);
                    void runWorkspaceAction('replay', api.replay, 'Historical OpenAI retirement replay loaded.');
                  }}
                >Replay historical incident
                </Button>
              </div>
            </>
          }
        >
          <div className="replay-modal-content">
            <div className="replay-date"><span>26</span><strong>March<br />2026</strong></div>
            <div>
              <h3>OpenAI gpt-4-0314 shutdown</h3>
              <p>Replay the documented model retirement against the example repository’s configured call sites. DriftCI will label its source receipts as historical replay.</p>
              <InlineNotice tone="warning">This event occurred in March 2026. The replay does not represent a newly announced production incident.</InlineNotice>
            </div>
          </div>
        </Modal>
      )}

      <div className="toast-region" aria-live="polite" aria-atomic="true">
        {toast && <Toast key={toast.id} toast={toast} onDismiss={dismissToast} />}
      </div>
    </div>
  );
}
