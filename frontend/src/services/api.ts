/**
 * API Service for Quality Governance Platform
 * Provides typed API calls with error handling and caching
 */

const API_BASE = import.meta.env.VITE_API_URL || 'https://qgp-backend-staging.azurewebsites.net/api/v1';

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  cache?: boolean;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// Simple in-memory cache
const cache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function apiRequest<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, cache: useCache = false } = options;
  
  const url = `${API_BASE}${endpoint}`;
  const cacheKey = `${method}:${url}`;
  
  // Check cache for GET requests
  if (useCache && method === 'GET') {
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data as T;
    }
  }
  
  const token = localStorage.getItem('access_token');
  
  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      errorData.detail || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }
  
  const data = await response.json();
  
  // Cache successful GET responses
  if (useCache && method === 'GET') {
    cache.set(cacheKey, { data, timestamp: Date.now() });
  }
  
  return data;
}

// ==================== Form Configuration API ====================

export interface FormFieldOption {
  value: string;
  label: string;
  sublabel?: string;
}

export interface FormField {
  id: number;
  name: string;
  label: string;
  field_type: string;
  order: number;
  placeholder?: string;
  help_text?: string;
  is_required: boolean;
  min_length?: number;
  max_length?: number;
  min_value?: number;
  max_value?: number;
  pattern?: string;
  default_value?: string;
  options?: FormFieldOption[];
  show_condition?: Record<string, unknown>;
  width: string;
}

export interface FormStep {
  id: number;
  name: string;
  description?: string;
  order: number;
  icon?: string;
  fields: FormField[];
  show_condition?: Record<string, unknown>;
}

export interface FormTemplate {
  id: number;
  name: string;
  slug: string;
  description?: string;
  form_type: string;
  version: number;
  is_active: boolean;
  is_published: boolean;
  icon?: string;
  color?: string;
  allow_drafts: boolean;
  allow_attachments: boolean;
  require_signature: boolean;
  auto_assign_reference: boolean;
  reference_prefix?: string;
  notify_on_submit: boolean;
  steps: FormStep[];
}

export interface Contract {
  id: number;
  name: string;
  code: string;
  description?: string;
  client_name?: string;
  is_active: boolean;
  display_order: number;
}

export interface LookupOption {
  id: number;
  category: string;
  code: string;
  label: string;
  description?: string;
  is_active: boolean;
  display_order: number;
}

export interface SystemSetting {
  key: string;
  value: string;
  category: string;
  description?: string;
  value_type: string;
}

// Form Templates
export const formTemplatesApi = {
  list: (formType?: string) =>
    apiRequest<{ items: FormTemplate[]; total: number }>(
      `/admin/config/templates${formType ? `?form_type=${formType}` : ''}`,
      { cache: true }
    ),
  
  getById: (id: number) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}`, { cache: true }),
  
  getBySlug: (slug: string) =>
    apiRequest<FormTemplate>(`/admin/config/templates/by-slug/${slug}`, { cache: true }),
  
  create: (data: Partial<FormTemplate>) =>
    apiRequest<FormTemplate>('/admin/config/templates', { method: 'POST', body: data }),
  
  update: (id: number, data: Partial<FormTemplate>) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}`, { method: 'PATCH', body: data }),
  
  publish: (id: number) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}/publish`, { method: 'POST' }),
  
  delete: (id: number) =>
    apiRequest<void>(`/admin/config/templates/${id}`, { method: 'DELETE' }),
};

// Contracts
export const contractsApi = {
  list: (activeOnly = true) =>
    apiRequest<{ items: Contract[]; total: number }>(
      `/admin/config/contracts${activeOnly ? '?is_active=true' : ''}`,
      { cache: true }
    ),
  
  create: (data: Partial<Contract>) =>
    apiRequest<Contract>('/admin/config/contracts', { method: 'POST', body: data }),
  
  update: (id: number, data: Partial<Contract>) =>
    apiRequest<Contract>(`/admin/config/contracts/${id}`, { method: 'PATCH', body: data }),
  
  delete: (id: number) =>
    apiRequest<void>(`/admin/config/contracts/${id}`, { method: 'DELETE' }),
};

// Lookup Options
export const lookupsApi = {
  list: (category: string, activeOnly = true) =>
    apiRequest<{ items: LookupOption[]; total: number }>(
      `/admin/config/lookup/${category}${activeOnly ? '?is_active=true' : ''}`,
      { cache: true }
    ),
  
  create: (category: string, data: Partial<LookupOption>) =>
    apiRequest<LookupOption>(`/admin/config/lookup/${category}`, { method: 'POST', body: data }),
  
  update: (category: string, id: number, data: Partial<LookupOption>) =>
    apiRequest<LookupOption>(`/admin/config/lookup/${category}/${id}`, { method: 'PATCH', body: data }),
  
  delete: (category: string, id: number) =>
    apiRequest<void>(`/admin/config/lookup/${category}/${id}`, { method: 'DELETE' }),
};

// System Settings
export const settingsApi = {
  list: (category?: string) =>
    apiRequest<{ items: SystemSetting[]; total: number }>(
      `/admin/config/settings${category ? `?category=${category}` : ''}`,
      { cache: true }
    ),
  
  get: (key: string) =>
    apiRequest<SystemSetting>(`/admin/config/settings/${key}`, { cache: true }),
  
  update: (key: string, value: string) =>
    apiRequest<SystemSetting>(`/admin/config/settings/${key}`, { method: 'PATCH', body: { value } }),
};

// Portal Submissions
export interface PortalSubmission {
  form_type: string;
  form_slug: string;
  data: Record<string, unknown>;
  draft_id?: string;
  attachments?: File[];
}

export const portalApi = {
  submitForm: (submission: PortalSubmission) =>
    apiRequest<{ reference_number: string; id: number }>('/portal/submit', {
      method: 'POST',
      body: submission,
    }),
  
  saveDraft: (formSlug: string, data: Record<string, unknown>) =>
    apiRequest<{ draft_id: string }>('/portal/drafts', {
      method: 'POST',
      body: { form_slug: formSlug, data },
    }),
  
  getDraft: (draftId: string) =>
    apiRequest<{ data: Record<string, unknown> }>(`/portal/drafts/${draftId}`),
  
  deleteDraft: (draftId: string) =>
    apiRequest<void>(`/portal/drafts/${draftId}`, { method: 'DELETE' }),
  
  trackSubmission: (referenceNumber: string) =>
    apiRequest<{
      reference_number: string;
      status: string;
      submitted_at: string;
      updates: Array<{ date: string; status: string; note: string }>;
    }>(`/portal/track/${referenceNumber}`),
};

// Utility for clearing cache
export function clearApiCache() {
  cache.clear();
}

export { ApiError };
