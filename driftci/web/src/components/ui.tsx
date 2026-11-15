import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  FileCode2,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  X,
  type LucideIcon,
} from 'lucide-react';
import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from 'react';
import type { CodeEvidence, Severity, SourceReceipt } from '../types';
import { cx, domain, formatDate, label, modeKind, modeLabel } from '../utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'small' | 'regular';
  icon?: LucideIcon;
  loading?: boolean;
}

export function Button({
  variant = 'secondary',
  size = 'regular',
  icon: Icon,
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx('button', `button-${variant}`, `button-${size}`, className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <LoaderCircle className="spin" aria-hidden="true" /> : Icon ? <Icon aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  label: string;
}

export function IconButton({ icon: Icon, label: accessibleLabel, className, ...props }: IconButtonProps) {
  return (
    <button className={cx('icon-button', className)} aria-label={accessibleLabel} title={accessibleLabel} {...props}>
      <Icon aria-hidden="true" />
    </button>
  );
}

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  return <span className={cx('badge', `severity-${severity}`)}>{label(severity)}</span>;
}

export function ModeBadge({ mode }: { mode: string }) {
  return (
    <span className={cx('badge mode-badge', `mode-${modeKind(mode)}`)}>
      <span className="status-dot" aria-hidden="true" />
      {modeLabel(mode)}
    </span>
  );
}

export function StateBadge({ state }: { state: string }) {
  return <span className={cx('badge state-badge', `state-${state}`)}>{label(state)}</span>;
}

export function Spinner({ label: loadingLabel = 'Loading workspace data' }: { label?: string }) {
  return (
    <div className="spinner" role="status">
      <LoaderCircle className="spin" aria-hidden="true" />
      <span>{loadingLabel}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon aria-hidden="true" /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ title = 'This view could not be loaded', message, onRetry, fullScreen = false }: {
  title?: string;
  message: string;
  onRetry?: () => void;
  fullScreen?: boolean;
}) {
  return (
    <div className={cx('error-state', fullScreen && 'error-state-full')}>
      <div className="error-symbol"><AlertCircle aria-hidden="true" /></div>
      <div className="error-state-copy">
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {onRetry && <Button icon={RotateCcw} onClick={onRetry}>Retry request</Button>}
    </div>
  );
}

export function PageHeading({ eyebrow, title, description, actions }: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function SectionHeading({ title, description, action }: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function CodeEvidence({ evidence }: { evidence: CodeEvidence[] }) {
  if (!evidence.length) {
    return <p className="muted-copy">No repository locations were returned for this item.</p>;
  }
  return (
    <div className="evidence-files">
      {evidence.map((item, index) => (
        <article className="code-evidence" key={`${item.file}:${item.line}:${index}`}>
          <div className="code-evidence-path">
            <FileCode2 aria-hidden="true" />
            <code>{item.file}<span>:{item.line}</span></code>
          </div>
          <pre><code>{item.snippet}</code></pre>
          <p>{item.reason}</p>
        </article>
      ))}
    </div>
  );
}

export function SourceReceiptCard({ receipt, compact = false }: { receipt: SourceReceipt; compact?: boolean }) {
  return (
    <article className={cx('source-receipt', compact && 'source-receipt-compact')}>
      <div className="receipt-topline">
        <span className="receipt-publisher"><ShieldCheck aria-hidden="true" />{receipt.publisher}</span>
        <ModeBadge mode={receipt.mode} />
      </div>
      <a className="receipt-title" href={receipt.url} target="_blank" rel="noreferrer noopener">
        {receipt.title}<ArrowUpRight aria-hidden="true" />
      </a>
      <div className="receipt-meta">
        <span>{domain(receipt.url)}</span>
        <span>Retrieved {formatDate(receipt.retrieved_at, true)}</span>
      </div>
      {receipt.quote && <blockquote>{receipt.quote}</blockquote>}
      <a className="source-link" href={receipt.url} target="_blank" rel="noreferrer noopener">
        Open primary source<ArrowUpRight aria-hidden="true" />
      </a>
    </article>
  );
}

interface DialogProps {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

function useDialog(onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    return () => {
      document.body.style.overflow = previousOverflow;
      dialog.close();
    };
  }, []);
  return { ref, onCancel: (event: React.SyntheticEvent<HTMLDialogElement>) => {
    event.preventDefault();
    onClose();
  } };
}

export function Drawer({ title, subtitle, onClose, children, footer, wide }: DialogProps) {
  const titleId = useId();
  const { ref, onCancel } = useDialog(onClose);
  return (
    <dialog
      ref={ref}
      className={cx('dialog drawer', wide && 'drawer-wide')}
      aria-labelledby={titleId}
      onCancel={onCancel}
      onClick={(event) => { if (event.target === ref.current) onClose(); }}
    >
      <div className="dialog-shell">
        <header className="dialog-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <IconButton icon={X} label="Close drawer" onClick={onClose} autoFocus />
        </header>
        <div className="dialog-body">{children}</div>
        {footer && <footer className="dialog-footer">{footer}</footer>}
      </div>
    </dialog>
  );
}

export function Modal({ title, subtitle, onClose, children, footer, wide }: DialogProps) {
  const titleId = useId();
  const { ref, onCancel } = useDialog(onClose);
  return (
    <dialog
      ref={ref}
      className={cx('dialog modal', wide && 'modal-wide')}
      aria-labelledby={titleId}
      onCancel={onCancel}
      onClick={(event) => { if (event.target === ref.current) onClose(); }}
    >
      <div className="dialog-shell">
        <header className="dialog-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <IconButton icon={X} label="Close dialog" onClick={onClose} autoFocus />
        </header>
        <div className="dialog-body">{children}</div>
        {footer && <footer className="dialog-footer">{footer}</footer>}
      </div>
    </dialog>
  );
}

export interface ToastData {
  id: number;
  message: string;
  tone: 'success' | 'error' | 'info';
}

export function Toast({ toast, onDismiss }: { toast: ToastData; onDismiss: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, toast.tone === 'error' ? 8000 : 4500);
    return () => window.clearTimeout(timer);
  }, [toast.id, toast.tone, onDismiss]);
  const Icon = toast.tone === 'success' ? CheckCircle2 : toast.tone === 'error' ? AlertCircle : Check;
  return (
    <div className={cx('toast', `toast-${toast.tone}`)} role={toast.tone === 'error' ? 'alert' : 'status'}>
      <Icon aria-hidden="true" />
      <span>{toast.message}</span>
      <IconButton icon={X} label="Dismiss notification" onClick={onDismiss} />
    </div>
  );
}

export function InlineNotice({ tone = 'info', children, ...props }: HTMLAttributes<HTMLDivElement> & {
  tone?: 'info' | 'warning' | 'error' | 'success';
}) {
  return <div className={cx('inline-notice', `notice-${tone}`)} {...props}>{children}</div>;
}
