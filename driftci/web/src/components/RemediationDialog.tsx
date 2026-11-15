import {
  Check,
  CheckCircle2,
  CircleAlert,
  Download,
  FileCode2,
  FileDiff,
  GitPullRequestArrow,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type { Remediation } from '../types';
import { cx, errorText, formatDate, plural } from '../utils';
import {
  Button,
  EmptyState,
  InlineNotice,
  Modal,
  SourceReceiptCard,
  StateBadge,
} from './ui';

interface RenderedDiffLine {
  type: 'addition' | 'deletion' | 'context' | 'hunk' | 'meta';
  content: string;
  oldLine: number | null;
  newLine: number | null;
}

function renderDiff(diff: string): RenderedDiffLine[] {
  let oldLine = 0;
  let newLine = 0;
  return diff.split('\n').map((content) => {
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(content);
    if (hunk) {
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
      return { type: 'hunk', content, oldLine: null, newLine: null };
    }
    if (content.startsWith('+') && !content.startsWith('+++')) {
      return { type: 'addition', content, oldLine: null, newLine: newLine++ };
    }
    if (content.startsWith('-') && !content.startsWith('---')) {
      return { type: 'deletion', content, oldLine: oldLine++, newLine: null };
    }
    if (content.startsWith(' ')) {
      return { type: 'context', content, oldLine: oldLine++, newLine: newLine++ };
    }
    return { type: 'meta', content, oldLine: null, newLine: null };
  });
}

export function RemediationDialog({ remediation, onChange, onClose, notify }: {
  remediation: Remediation;
  onChange: (remediation: Remediation) => void;
  onClose: () => void;
  notify: (message: string, tone?: 'success' | 'error' | 'info') => void;
}) {
  const [selectedPath, setSelectedPath] = useState(remediation.files[0]?.path ?? '');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setSelectedPath(remediation.files[0]?.path ?? '');
    setError('');
    setBusy('');
  }, [remediation.id, remediation.files]);

  const selectedFile = remediation.files.find((file) => file.path === selectedPath) ?? remediation.files[0];
  const diffLines = useMemo(() => selectedFile ? renderDiff(selectedFile.diff) : [], [selectedFile]);

  const approve = async () => {
    setBusy('approve');
    setError('');
    try {
      const updated = await api.approveRemediation(remediation.id);
      onChange(updated);
      notify('Human approval recorded. No merge or deployment was performed.', 'success');
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy('');
    }
  };

  const exportPatch = async () => {
    setBusy('export');
    setError('');
    try {
      const patch = await api.patch(remediation.id);
      const blob = new Blob([patch], { type: 'text/x-patch;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${remediation.id}.patch`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      notify('Unified patch downloaded.', 'success');
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy('');
    }
  };

  const openPr = async () => {
    setBusy('pr');
    setError('');
    try {
      const updated = await api.openPr(remediation.id);
      onChange(updated);
      if (updated.pr_url) window.open(updated.pr_url, '_blank', 'noopener,noreferrer');
      notify(updated.pr_url ? 'Pull request created for human review.' : 'Pull request request completed.', 'success');
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy('');
    }
  };

  return (
    <Modal
      title="Review remediation"
      subtitle={`${remediation.id} · Human review required`}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="remediation-export-copy">
            <strong>{remediation.can_open_pr ? 'GitHub integration available' : 'Patch export mode'}</strong>
            <span>{remediation.can_open_pr ? 'Create a pull request only after approval.' : 'GitHub credentials are not configured; download the real patch.'}</span>
          </div>
          <div className="dialog-footer-actions">
            <Button icon={Download} disabled={!remediation.approved_at} title={!remediation.approved_at ? 'Approve this remediation before exporting its patch' : undefined} loading={busy === 'export'} onClick={() => void exportPatch()}>Export patch</Button>
            {remediation.pr_url ? (
              <a className="button button-secondary button-regular" href={remediation.pr_url} target="_blank" rel="noreferrer noopener">
                <GitPullRequestArrow aria-hidden="true" /><span>View PR #{remediation.pr_number ?? ''}</span>
              </a>
            ) : remediation.can_open_pr ? (
              <Button icon={GitPullRequestArrow} disabled={!remediation.approved_at} title={!remediation.approved_at ? 'Approve this remediation before opening a pull request' : undefined} loading={busy === 'pr'} onClick={() => void openPr()}>Open pull request</Button>
            ) : null}
            {remediation.approved_at ? (
              <span className="approved-label"><CheckCircle2 aria-hidden="true" />Approved {formatDate(remediation.approved_at, true)}</span>
            ) : (
              <Button variant="primary" icon={Check} loading={busy === 'approve'} onClick={() => void approve()}>Approve remediation</Button>
            )}
          </div>
        </>
      }
    >
      <div className="remediation-heading">
        <div className="remediation-icon"><FileDiff aria-hidden="true" /></div>
        <div>
          <div className="remediation-badges"><StateBadge state={remediation.status} /><span>Created {formatDate(remediation.created_at, true)}</span></div>
          <h3>{remediation.title}</h3>
          <p>{remediation.summary}</p>
        </div>
      </div>

      <InlineNotice tone="info">
        <ShieldCheck aria-hidden="true" />
        <div><strong>Approval records a review decision only.</strong><p>DriftCI does not silently merge or deploy. Inspect every changed line and complete the pending application checks in your own CI workflow.</p></div>
      </InlineNotice>
      {error && <InlineNotice tone="error" role="alert">{error}</InlineNotice>}

      <section className="remediation-checks">
        <div className="section-heading"><div><h3>Targeted checks</h3><p>{plural(remediation.checks.length, 'check')} returned with this patch</p></div></div>
        {remediation.checks.length ? (
          <div className="check-result-grid">
            {remediation.checks.map((check) => (
              <article key={check.name} className={cx('check-result', check.status === 'passed' ? 'check-passed' : 'check-attention')}>
                {check.status === 'passed' ? <CheckCircle2 aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
                <div><strong>{check.name}</strong><p>{check.detail}</p></div>
                <StateBadge state={check.status} />
              </article>
            ))}
          </div>
        ) : <p className="muted-copy">No targeted checks were returned. Review and test this patch manually.</p>}
      </section>

      <section className="diff-section">
        <div className="section-heading"><div><h3>Unified diff</h3><p>Exact server-generated changes, with repository paths and line context.</p></div></div>
        {selectedFile ? (
          <div className="diff-workspace">
            <div className="diff-file-tabs" role="tablist" aria-label="Changed files">
              {remediation.files.map((file) => (
                <button
                  role="tab"
                  aria-selected={selectedFile.path === file.path}
                  className={cx(selectedFile.path === file.path && 'active')}
                  key={file.path}
                  onClick={() => setSelectedPath(file.path)}
                >
                  <FileCode2 aria-hidden="true" /><code>{file.path}</code><span className="diff-add">+{file.additions}</span><span className="diff-delete">−{file.deletions}</span>
                </button>
              ))}
            </div>
            <div className="diff-file-header">
              <code>{selectedFile.path}</code>
              <span><strong className="diff-add">+{selectedFile.additions}</strong><strong className="diff-delete">−{selectedFile.deletions}</strong></span>
            </div>
            <div className="diff-code" role="region" aria-label={`Unified diff for ${selectedFile.path}`} tabIndex={0}>
              <table>
                <tbody>
                  {diffLines.map((line, index) => (
                    <tr className={`diff-line-${line.type}`} key={`${index}:${line.content}`}>
                      <td className="diff-line-number">{line.oldLine ?? ''}</td>
                      <td className="diff-line-number">{line.newLine ?? ''}</td>
                      <td className="diff-line-content"><code>{line.content || ' '}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <EmptyState icon={FileCode2} title="No changed files returned" description="The remediation contains no file diff to inspect. Export is still available if the API provides a patch." />}
      </section>

      {remediation.source_receipts.length > 0 && (
        <section className="remediation-sources">
          <div className="section-heading"><div><h3>Remediation citations</h3><p>Official sources used to produce this change.</p></div></div>
          <div className="receipt-grid">{remediation.source_receipts.map((receipt, index) => <SourceReceiptCard key={`${receipt.url}:${index}`} receipt={receipt} compact />)}</div>
        </section>
      )}
    </Modal>
  );
}
