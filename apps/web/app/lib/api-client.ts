
'use client';

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

export type Workspace = { id: string; name: string; slug: string; role: string };
export type SessionState = {
  accessToken: string;
  refreshToken: string;
  user: { id: string; email: string; name: string; role?: string };
  workspace: { organization_id: string; role: string };
  workspaces: Workspace[];
};

export type ApiResult<T> = { data?: T; error?: string; requestId?: string };

async function parseResponse<T>(response: Response): Promise<ApiResult<T>> {
  const requestId = response.headers.get('x-request-id') || undefined;
  const text = await response.text();
  let payload: unknown = undefined;
  try { payload = text ? JSON.parse(text) : undefined; } catch { payload = text; }
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload && 'detail' in payload ? String((payload as {detail: unknown}).detail) : response.statusText;
    return { error: detail, requestId };
  }
  return { data: payload as T, requestId };
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, token?: string): Promise<ApiResult<T>> {
  const headers = new Headers(options.headers);
  headers.set('content-type', headers.get('content-type') || 'application/json');
  if (token) headers.set('authorization', `Bearer ${token}`);
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers, cache: 'no-store' });
    return parseResponse<T>(response);
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'API unavailable' };
  }
}

export async function login(email = 'admin@voxrelay.demo', password = 'DemoPass123!') {
  return apiRequest<SessionState>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
}

export async function switchWorkspace(token: string, organization_id: string) {
  return apiRequest<SessionState>('/api/v1/auth/switch-workspace', { method: 'POST', body: JSON.stringify({ organization_id }) }, token);
}

export async function startSimulation(token: string, agentId = 'agent-clinic', scenario = 'clinic_booking') {
  return apiRequest<{ call: { id: string; status: string; caller_name: string } }>(`/api/v1/voice-agents/${agentId}/simulate`, { method: 'POST', body: JSON.stringify({ scenario }) }, token);
}

export async function listCalls(token: string) { return apiRequest<{ items: any[]; total: number }>('/api/v1/calls?limit=20', {}, token); }
export async function callDetail(token: string, id: string) { return apiRequest<any>(`/api/v1/calls/${id}`, {}, token); }
export async function listLeads(token: string) { return apiRequest<{ items: any[]; total: number }>('/api/v1/leads?limit=40', {}, token); }
export async function listAppointments(token: string) { return apiRequest<{ items: any[]; total: number }>('/api/v1/appointments?limit=40', {}, token); }
export async function listReports(token: string) { return apiRequest<{ items: any[] }>('/api/v1/reports', {}, token); }
export async function listProviders(token: string) { return apiRequest<{ items: any[] }>('/api/v1/providers', {}, token); }
export async function platformOperations(token: string) { return apiRequest<any>('/api/v1/platform/operations', {}, token); }
export async function searchGlobal(token: string, q: string) { return apiRequest<{ items: any[] }>(`/api/v1/search?q=${encodeURIComponent(q)}`, {}, token); }
export async function mutate(token: string, path: string, body: unknown = {}) { return apiRequest<any>(path, { method: 'POST', body: JSON.stringify(body) }, token); }
