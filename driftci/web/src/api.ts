import type {
  ActionStatus,
  Bootstrap,
  Health,
  Incident,
  IncidentsResponse,
  Remediation,
  Signal,
} from './types';

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

function errorMessage(payload: unknown, status: number) {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = payload.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) return String(item.msg);
        return String(item);
      }).join('; ');
    }
  }
  return `The API returned ${status}. Check the backend and try again.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('Cannot reach the DriftCI API. Make sure the backend is running on port 8100.', 0);
  }

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new ApiError(errorMessage(payload, response.status), response.status);
  }

  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) return response.json() as Promise<T>;
  return response.text() as Promise<T>;
}

const post = <T>(path: string, body?: unknown, signal?: AbortSignal) => request<T>(path, {
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
  signal,
});

export const api = {
  health: () => request<Health>('/health'),
  bootstrap: () => request<Bootstrap>('/bootstrap'),
  signals: (kind = '', severity = '', signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (kind) params.set('kind', kind);
    if (severity) params.set('severity', severity);
    const query = params.size ? `?${params}` : '';
    return request<Signal[]>(`/signals${query}`, { signal });
  },
  signal: (id: string) => request<Signal>(`/signals/${encodeURIComponent(id)}`),
  setSignalState: (id: string, state: 'acknowledged' | 'resolved' | 'monitoring' | 'needs_action') => post<Signal>(`/signals/${encodeURIComponent(id)}/state`, { state }),
  addWatch: (url: string, title: string) => post<Bootstrap>('/watches', { url, title }),
  removeWatch: (key: string) => request<Bootstrap>(`/watches/${encodeURIComponent(key)}`, { method: 'DELETE' }),
  scan: () => post<Bootstrap>('/scan'),
  replay: () => post<Bootstrap>('/demo/replay'),
  resetReplay: () => post<Bootstrap>('/demo/reset'),
  incidents: (signal?: AbortSignal) => request<IncidentsResponse>('/incidents', { signal }),
  incidentReport: (id: string) => request<string>(`/incidents/${encodeURIComponent(id)}/report`, {
    headers: { Accept: 'text/markdown' },
  }).then((value) => String(value)),
  setIncidentAction: (incidentId: string, actionId: string, status: ActionStatus) =>
    post<Incident>(`/incidents/${encodeURIComponent(incidentId)}/actions/${encodeURIComponent(actionId)}`, { status }),
  createRemediation: (signalId: string) => post<Remediation>('/remediations', { signal_id: signalId }),
  approveRemediation: (id: string) => post<Remediation>(`/remediations/${encodeURIComponent(id)}/approve`),
  openPr: (id: string) => post<Remediation>(`/remediations/${encodeURIComponent(id)}/open-pr`),
  patch: (id: string) => request<string>(`/remediations/${encodeURIComponent(id)}/patch`, {
    headers: { Accept: 'text/x-patch' },
  }).then((value) => String(value)),
  connectRepository: (url: string) => post<Bootstrap>('/repositories/connect', { url }),
  restoreWorkspace: () => request<Bootstrap>('/workspace', { method: 'DELETE' }),
};
