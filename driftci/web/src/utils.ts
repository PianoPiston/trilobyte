import type { Severity } from './types';

export const cx = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');

export const label = (value: string) => value
  .replaceAll('_', ' ')
  .replaceAll('-', ' ')
  .replace(/\b\w/g, (character) => character.toUpperCase());

export function formatDate(value: string | null, includeTime = false) {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(includeTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(date);
}

export function relativeTime(value: string | null) {
  if (!value) return 'Never checked';
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return value;
  const seconds = Math.round((timestamp - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 60) return 'Just now';
  if (absolute > 7 * 86400) return formatDate(value);
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  if (absolute < 3600) return formatter.format(Math.round(seconds / 60), 'minute');
  if (absolute < 86400) return formatter.format(Math.round(seconds / 3600), 'hour');
  return formatter.format(Math.round(seconds / 86400), 'day');
}

export function modeKind(mode: string) {
  const normalized = mode.toLowerCase();
  if (normalized.includes('replay') || normalized.includes('historical')) return 'replay';
  if (normalized.includes('live')) return 'live';
  if (normalized.includes('cache')) return 'cached';
  if (normalized.includes('demo') || normalized.includes('controlled')) return 'demo';
  return 'neutral';
}

export function modeLabel(mode: string) {
  const kind = modeKind(mode);
  if (kind === 'replay') return 'Historical replay';
  if (kind === 'live') return 'Live';
  if (kind === 'cached') return 'Cached';
  if (kind === 'demo') return 'Controlled demo';
  return label(mode);
}

export function domain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export const severityRank: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

export function plural(count: number, singular: string, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

export function responseDuration(start: string, end: string | null) {
  if (!end) return null;
  const milliseconds = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return null;
  const hours = milliseconds / 3_600_000;
  if (hours < 1) return `${Math.max(1, Math.round(milliseconds / 60_000))} min response`;
  if (hours < 48) return `${hours.toFixed(hours < 10 ? 1 : 0)} h response`;
  return `${(hours / 24).toFixed(1)} d response`;
}

export function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Try again.';
}

export function fileName(path: string) {
  return path.split('/').pop() ?? path;
}
