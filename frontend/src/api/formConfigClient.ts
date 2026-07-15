/**
 * Admin form configuration API client — templates, steps, and fields.
 * Uses the shared axios instance (auth interceptors) from client.ts.
 */
import type { AxiosInstance } from 'axios'
import api from './client'

export interface FormFieldOption {
  value: string
  label: string
}

export interface FormFieldPayload {
  name: string
  label: string
  field_type: string
  order?: number
  placeholder?: string
  help_text?: string
  is_required?: boolean
  options?: FormFieldOption[]
  width?: string
}

export interface FormFieldResponse extends FormFieldPayload {
  id: number
  step_id: number
  created_at: string
  updated_at: string
}

export interface FormStepPayload {
  name: string
  description?: string
  order?: number
  icon?: string
  fields?: FormFieldPayload[]
}

export interface FormStepResponse extends Omit<FormStepPayload, 'fields'> {
  id: number
  template_id: number
  fields: FormFieldResponse[]
  created_at: string
  updated_at: string
}

export interface FormTemplatePayload {
  name: string
  slug: string
  description?: string
  form_type: string
  icon?: string
  color?: string
  allow_drafts?: boolean
  allow_attachments?: boolean
  require_signature?: boolean
  auto_assign_reference?: boolean
  reference_prefix?: string
  notify_on_submit?: boolean
  notification_emails?: string
  workflow_id?: number
  steps?: FormStepPayload[]
}

export interface FormTemplateUpdatePayload {
  name?: string
  slug?: string
  description?: string
  form_type?: string
  icon?: string
  color?: string
  allow_drafts?: boolean
  allow_attachments?: boolean
  require_signature?: boolean
  auto_assign_reference?: boolean
  reference_prefix?: string
  notify_on_submit?: boolean
  notification_emails?: string
  workflow_id?: number
  is_active?: boolean
  is_published?: boolean
}

export interface FormTemplateResponse extends FormTemplatePayload {
  id: number
  version: number
  is_active: boolean
  is_published: boolean
  published_at?: string | null
  steps: FormStepResponse[]
  created_at: string
  updated_at: string
}

export interface FormTemplateListResponse {
  items: FormTemplateResponse[]
  total: number
  page: number
  page_size: number
}

export interface FormTemplateListItem {
  id: number
  name: string
  slug: string
  form_type: string
  description?: string
  is_active: boolean
  is_published: boolean
  version: number
  steps_count: number
  fields_count: number
  updated_at: string
}

const BASE = '/api/v1/admin/config'

function toListItem(template: FormTemplateResponse): FormTemplateListItem {
  const steps = template.steps ?? []
  return {
    id: template.id,
    name: template.name,
    slug: template.slug,
    form_type: template.form_type,
    description: template.description,
    is_active: template.is_active,
    is_published: template.is_published,
    version: template.version,
    steps_count: steps.length,
    fields_count: steps.reduce((sum, step) => sum + (step.fields?.length ?? 0), 0),
    updated_at: template.updated_at,
  }
}

export function createFormConfigApi(axios: AxiosInstance) {
  return {
    listTemplates: (params?: { form_type?: string; is_active?: boolean; page?: number; page_size?: number }) => {
      const search = new URLSearchParams()
      if (params?.form_type) search.set('form_type', params.form_type)
      if (params?.is_active !== undefined) search.set('is_active', String(params.is_active))
      if (params?.page) search.set('page', String(params.page))
      if (params?.page_size) search.set('page_size', String(params.page_size))
      const qs = search.toString()
      return axios
        .get<FormTemplateListResponse>(`${BASE}/templates${qs ? `?${qs}` : ''}`)
        .then((r) => ({
          ...r.data,
          items: r.data.items.map(toListItem),
        }))
    },

    getTemplate: (id: number) =>
      axios.get<FormTemplateResponse>(`${BASE}/templates/${id}`).then((r) => r.data),

    createTemplate: (data: FormTemplatePayload) =>
      axios.post<FormTemplateResponse>(`${BASE}/templates`, data).then((r) => r.data),

    updateTemplate: (id: number, data: FormTemplateUpdatePayload) =>
      axios.patch<FormTemplateResponse>(`${BASE}/templates/${id}`, data).then((r) => r.data),

    publishTemplate: (id: number) =>
      axios.post<FormTemplateResponse>(`${BASE}/templates/${id}/publish`).then((r) => r.data),

    deleteTemplate: (id: number) =>
      axios.delete<void>(`${BASE}/templates/${id}`).then((r) => r.data),

    createStep: (templateId: number, data: FormStepPayload) =>
      axios
        .post<FormStepResponse>(`${BASE}/templates/${templateId}/steps`, data)
        .then((r) => r.data),

    updateStep: (stepId: number, data: Partial<FormStepPayload>) =>
      axios.patch<FormStepResponse>(`${BASE}/steps/${stepId}`, data).then((r) => r.data),

    deleteStep: (stepId: number) =>
      axios.delete<void>(`${BASE}/steps/${stepId}`).then((r) => r.data),

    createField: (stepId: number, data: FormFieldPayload) =>
      axios.post<FormFieldResponse>(`${BASE}/steps/${stepId}/fields`, data).then((r) => r.data),

    updateField: (fieldId: number, data: Partial<FormFieldPayload>) =>
      axios.patch<FormFieldResponse>(`${BASE}/fields/${fieldId}`, data).then((r) => r.data),

    deleteField: (fieldId: number) =>
      axios.delete<void>(`${BASE}/fields/${fieldId}`).then((r) => r.data),
  }
}

export const formConfigApi = createFormConfigApi(api)
