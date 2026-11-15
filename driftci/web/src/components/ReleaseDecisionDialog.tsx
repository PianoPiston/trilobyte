import { CheckCheck, Pause, ShieldCheck } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { PullRequest } from '../types';
import { errorText } from '../utils';
import { Button, InlineNotice, Modal } from './ui';

export function ReleaseDecisionDialog({ pr, githubStale, onClose, onSubmit }: {
  pr: PullRequest;
  githubStale: boolean;
  onClose: () => void;
  onSubmit: (decision: 'ready' | 'hold', reviewer: string, note: string) => Promise<void>;
}) {
  const [reviewer, setReviewer] = useState(pr.release_decision?.reviewer ?? '');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const checks = pr.check_summary.state;
  const checksBlock = checks === 'pending' || checks === 'failed';
  const readyDisabled = githubStale || !pr.detail_complete || checksBlock || pr.state !== 'open';

  const submit = async (decision: 'ready' | 'hold') => {
    if (!reviewer.trim()) {
      setError('Enter the name of the person making this decision.');
      return;
    }
    setBusy(decision);
    setError('');
    try {
      await onSubmit(decision, reviewer.trim(), note.trim());
    } catch (requestError) {
      setError(errorText(requestError));
      setBusy('');
    }
  };

  const formSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(readyDisabled ? 'hold' : 'ready');
  };

  return (
    <Modal
      title="Record a release decision"
      subtitle={`Local review · PR #${pr.number} · ${pr.head_sha.slice(0, 10)}`}
      onClose={onClose}
      wide
    >
      <form id={`decision-${pr.id}`} onSubmit={formSubmit}>
        <div className="decision-scope-intro">
          <ShieldCheck aria-hidden="true" />
          <div>
            <strong>One person, one evidence snapshot.</strong>
            <p>This records a DriftCI decision for head <code>{pr.head_sha.slice(0, 10)}</code> and evidence <code>{pr.evidence_hash}</code>. A later head or matching external change makes it stale.</p>
          </div>
        </div>
        <InlineNotice tone="info" className="decision-scope-note">
          This does not approve or merge the GitHub pull request. GitHub reviews and DriftCI release decisions remain separate records.
        </InlineNotice>
        {githubStale && (
          <InlineNotice tone="warning" className="decision-scope-note">
            GitHub release evidence is stale or has not been retrieved. Refresh the source before recording ready, or preserve this limitation with a pause.
          </InlineNotice>
        )}
        {(!pr.detail_complete || checksBlock) && (
          <InlineNotice tone="warning" className="decision-scope-note">
            {!pr.detail_complete
              ? 'PR file, review or check coverage is incomplete. Refresh the release before recording ready, or pause with the known coverage limit.'
              : checks === 'pending'
                ? 'CI checks are still running. Wait for them to finish, or record a pause.'
                : 'At least one check is failing. Inspect it before recording ready, or record a pause.'}
          </InlineNotice>
        )}
        {checks === 'none' && <p className="decision-check-footnote">GitHub reported no checks for this head. Recording ready will preserve that limitation in the decision receipt.</p>}
        <div className="decision-form-fields">
          <label htmlFor={`reviewer-${pr.id}`}>Decision owner</label>
          <input
            id={`reviewer-${pr.id}`}
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
            maxLength={80}
            required
            placeholder="Your name"
            autoComplete="name"
          />
          <label htmlFor={`note-${pr.id}`}>Evidence notes <span>Optional</span></label>
          <textarea
            id={`note-${pr.id}`}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={1000}
            rows={4}
            placeholder="Which external changes, checks and remaining limitations did you review?"
          />
          <span className="field-character-count">{note.length} / 1000</span>
        </div>
        {error && <InlineNotice tone="error" role="alert">{error}</InlineNotice>}
        <div className="decision-form-actions">
          <Button icon={Pause} loading={busy === 'hold'} onClick={() => void submit('hold')} type="button">Pause release</Button>
          <Button variant="primary" icon={CheckCheck} loading={busy === 'ready'} disabled={readyDisabled} onClick={() => void submit('ready')} type="button">Record ready</Button>
        </div>
      </form>
    </Modal>
  );
}
