/**
 * @deprecated This module is deprecated. Use `../api/client` instead.
 * All types and API objects have been migrated to the primary axios-based client.
 * This file is kept for backward compatibility but should not be used for new code.
 */

import { API_BASE_URL } from "../config/apiBase";

// Use centralized API base URL
const API_BASE = API_BASE_URL;

interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  cache?: boolean;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Simple in-memory cache
const cache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function apiRequest<T>(
  endpoint: string,
  options: ApiOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    headers = {},
    cache: useCache = false,
  } = options;

  const url = `${API_BASE}${endpoint}`;
  const cacheKey = `${method}:${url}`;

  // Check cache for GET requests
  if (useCache && method === "GET") {
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data as T;
    }
  }

  const token = localStorage.getItem("access_token");

  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
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
      errorData,
    );
  }

  const data = await response.json();

  // Cache successful GET responses
  if (useCache && method === "GET") {
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
  steps_count?: number;
  fields_count?: number;
  updated_at?: string;
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
  is_editable?: boolean;
}

// Form Templates
export const formTemplatesApi = {
  list: (formType?: string) =>
    apiRequest<{ items: FormTemplate[]; total: number }>(
      `/admin/config/templates${formType ? `?form_type=${formType}` : ""}`,
      { cache: true },
    ),

  getById: (id: number) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}`, { cache: true }),

  getBySlug: (slug: string) =>
    apiRequest<FormTemplate>(`/admin/config/templates/by-slug/${slug}`, {
      cache: true,
    }),

  create: (data: Partial<FormTemplate>) =>
    apiRequest<FormTemplate>("/admin/config/templates", {
      method: "POST",
      body: data,
    }),

  update: (id: number, data: Partial<FormTemplate>) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}`, {
      method: "PATCH",
      body: data,
    }),

  publish: (id: number) =>
    apiRequest<FormTemplate>(`/admin/config/templates/${id}/publish`, {
      method: "POST",
    }),

  delete: (id: number) =>
    apiRequest<void>(`/admin/config/templates/${id}`, { method: "DELETE" }),
};

// Contracts
export const contractsApi = {
  list: (activeOnly = true) =>
    apiRequest<{ items: Contract[]; total: number }>(
      `/admin/config/contracts${activeOnly ? "?is_active=true" : ""}`,
      { cache: true },
    ),

  create: (data: Partial<Contract>) =>
    apiRequest<Contract>("/admin/config/contracts", {
      method: "POST",
      body: data,
    }),

  update: (id: number, data: Partial<Contract>) =>
    apiRequest<Contract>(`/admin/config/contracts/${id}`, {
      method: "PATCH",
      body: data,
    }),

  delete: (id: number) =>
    apiRequest<void>(`/admin/config/contracts/${id}`, { method: "DELETE" }),
};

// Lookup Options
export const lookupsApi = {
  list: (category: string, activeOnly = true) =>
    apiRequest<{ items: LookupOption[]; total: number }>(
      `/admin/config/lookup/${category}${activeOnly ? "?is_active=true" : ""}`,
      { cache: true },
    ),

  create: (category: string, data: Partial<LookupOption>) =>
    apiRequest<LookupOption>(`/admin/config/lookup/${category}`, {
      method: "POST",
      body: data,
    }),

  update: (category: string, id: number, data: Partial<LookupOption>) =>
    apiRequest<LookupOption>(`/admin/config/lookup/${category}/${id}`, {
      method: "PATCH",
      body: data,
    }),

  delete: (category: string, id: number) =>
    apiRequest<void>(`/admin/config/lookup/${category}/${id}`, {
      method: "DELETE",
    }),
};

// System Settings
export const settingsApi = {
  list: (category?: string) =>
    apiRequest<{ items: SystemSetting[]; total: number }>(
      `/admin/config/settings${category ? `?category=${category}` : ""}`,
      { cache: true },
    ),

  get: (key: string) =>
    apiRequest<SystemSetting>(`/admin/config/settings/${key}`, { cache: true }),

  update: (key: string, value: string) =>
    apiRequest<SystemSetting>(`/admin/config/settings/${key}`, {
      method: "PATCH",
      body: { value },
    }),
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
    apiRequest<{ reference_number: string; id: number }>("/portal/submit", {
      method: "POST",
      body: submission,
    }),

  saveDraft: (formSlug: string, data: Record<string, unknown>) =>
    apiRequest<{ draft_id: string }>("/portal/drafts", {
      method: "POST",
      body: { form_slug: formSlug, data },
    }),

  getDraft: (draftId: string) =>
    apiRequest<{ data: Record<string, unknown> }>(`/portal/drafts/${draftId}`),

  deleteDraft: (draftId: string) =>
    apiRequest<void>(`/portal/drafts/${draftId}`, { method: "DELETE" }),

  trackSubmission: (referenceNumber: string) =>
    apiRequest<{
      reference_number: string;
      status: string;
      submitted_at: string;
      updates: Array<{ date: string; status: string; note: string }>;
    }>(`/portal/track/${referenceNumber}`),
};

// ==================== Near Miss API ====================

export interface NearMissCreate {
  reporter_name: string;
  reporter_email?: string;
  reporter_phone?: string;
  reporter_role?: string;
  was_involved: boolean;
  contract: string;
  contract_other?: string;
  location: string;
  location_coordinates?: string;
  event_date: string;
  event_time?: string;
  description: string;
  potential_consequences?: string;
  preventive_action_suggested?: string;
  persons_involved?: string;
  witnesses_present: boolean;
  witness_names?: string;
  asset_number?: string;
  asset_type?: string;
  risk_category?: string;
  potential_severity?: string;
  attachments?: string;
}

export interface NearMissResponse extends NearMissCreate {
  id: number;
  reference_number: string;
  status: string;
  priority: string;
  created_at: string;
  updated_at: string;
}

export const nearMissApi = {
  create: (data: NearMissCreate) =>
    apiRequest<NearMissResponse>("/near-misses/", {
      method: "POST",
      body: data,
    }),

  list: (page = 1, pageSize = 20, status?: string, contract?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.append("status", status);
    if (contract) params.append("contract", contract);
    return apiRequest<{
      items: NearMissResponse[];
      total: number;
      page: number;
      pages: number;
    }>(`/near-misses/?${params.toString()}`);
  },

  get: (id: number) => apiRequest<NearMissResponse>(`/near-misses/${id}`),

  update: (id: number, data: Partial<NearMissCreate>) =>
    apiRequest<NearMissResponse>(`/near-misses/${id}`, {
      method: "PATCH",
      body: data,
    }),

  delete: (id: number) =>
    apiRequest<void>(`/near-misses/${id}`, { method: "DELETE" }),
};

// ==================== Incidents API ====================

export interface IncidentCreate {
  title: string;
  description: string;
  severity: string;
  incident_date: string;
  location: string;
  reported_by: string;
  contract?: string;
  injuries_occurred?: boolean;
  injury_details?: string;
  witnesses?: string;
  attachments?: string;
}

export interface IncidentResponse extends IncidentCreate {
  id: number;
  reference_number: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const incidentsApi = {
  create: (data: IncidentCreate) =>
    apiRequest<IncidentResponse>("/incidents/", { method: "POST", body: data }),

  list: (page = 1, pageSize = 20, status?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.append("status", status);
    return apiRequest<{ items: IncidentResponse[]; total: number }>(
      `/incidents/?${params.toString()}`,
    );
  },

  get: (id: number) => apiRequest<IncidentResponse>(`/incidents/${id}`),

  update: (id: number, data: Partial<IncidentCreate>) =>
    apiRequest<IncidentResponse>(`/incidents/${id}`, {
      method: "PATCH",
      body: data,
    }),
};

// ==================== RTA API ====================

export interface RTACreate {
  title: string;
  description: string;
  severity: string;
  collision_date: string;
  reported_date: string;
  location: string;
  company_vehicle_registration?: string;
  company_vehicle_make_model?: string;
  company_vehicle_damage?: string;
  driver_name?: string;
  driver_statement?: string;
  driver_injured?: boolean;
  driver_injury_details?: string;
  third_parties?: Record<string, unknown>[];
  vehicles_involved_count?: number;
  witnesses?: string;
  witnesses_structured?: Record<string, unknown>[];
  weather_conditions?: string;
  road_conditions?: string;
  lighting_conditions?: string;
  police_attended?: boolean;
  police_reference?: string;
  cctv_available?: boolean;
  cctv_location?: string;
  dashcam_footage_available?: boolean;
  footage_secured?: boolean;
  footage_notes?: string;
  attachments?: string;
}

export interface RTAResponse extends RTACreate {
  id: number;
  reference_number: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const rtasApi = {
  create: (data: RTACreate) =>
    apiRequest<RTAResponse>("/rtas/", { method: "POST", body: data }),

  list: (page = 1, pageSize = 20, status?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.append("status", status);
    return apiRequest<{ items: RTAResponse[]; total: number }>(
      `/rtas/?${params.toString()}`,
    );
  },

  get: (id: number) => apiRequest<RTAResponse>(`/rtas/${id}`),

  update: (id: number, data: Partial<RTACreate>) =>
    apiRequest<RTAResponse>(`/rtas/${id}`, { method: "PATCH", body: data }),
};

// ==================== Complaints API ====================

export interface ComplaintCreate {
  title: string;
  description: string;
  category: string;
  priority: string;
  complainant_name: string;
  complainant_email?: string;
  complainant_phone?: string;
  contract?: string;
  attachments?: string;
}

export interface ComplaintResponse extends ComplaintCreate {
  id: number;
  reference_number: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const complaintsApi = {
  create: (data: ComplaintCreate) =>
    apiRequest<ComplaintResponse>("/complaints/", {
      method: "POST",
      body: data,
    }),

  list: (page = 1, pageSize = 20, status?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.append("status", status);
    return apiRequest<{ items: ComplaintResponse[]; total: number }>(
      `/complaints/?${params.toString()}`,
    );
  },

  get: (id: number) => apiRequest<ComplaintResponse>(`/complaints/${id}`),

  update: (id: number, data: Partial<ComplaintCreate>) =>
    apiRequest<ComplaintResponse>(`/complaints/${id}`, {
      method: "PATCH",
      body: data,
    }),
};

// Utility for clearing cache
export function clearApiCache() {
  cache.clear();
}

export { ApiError };
