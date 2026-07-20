import type { AxiosInstance } from 'axios'

export const ATLAS_HUB_URL =
  'https://www.atlas-hub.co.uk/o/98b88f4e-2c3f-44c1-a812-36ea66222c7d/'

export type TrainingMatrixImport = {
  id: number
  filename: string
  status: string
  person_count: number
  course_count: number
  cell_count: number
  nonempty_cell_count: number
  expiry_without_passed_count: number
  created_at?: string
}

export type TrainingMatrixImportQa = {
  import_id: number
  expiry_without_passed_count: number
  expiry_without_passed_before_today: number
  expiry_without_passed_after_today: number
  expiry_without_passed_before_pct: number
  expiry_without_passed_after_pct: number
  all_expiry_count: number
  all_expiry_before_today: number
  all_expiry_after_today: number
  all_expiry_before_pct: number
  all_expiry_after_pct: number
}

export type TrainingMatrixComplianceRow = {
  atlas_name: string
  department?: string | null
  engineer_id?: number | null
  engineer_display_name?: string | null
  course_key: string
  course_display_name: string
  frequency_years: number
  status: string
  atlas_status?: string | null
  passed_on?: string | null
  expires_on?: string | null
  qgp_due_on?: string | null
  expiry_without_passed: boolean
  atlas_hub_url: string
}

export type TrainingMatrixRequirement = {
  id: number
  match_department?: string | null
  match_role_key?: string | null
  course_key: string
  course_display_name: string
  frequency_years: number
  is_active: boolean
  notes?: string | null
}

export type TrainingMatrixNameMapItem = {
  atlas_name: string
  department?: string | null
  engineer_id?: number | null
  engineer_display_name?: string | null
  mapped: boolean
}

export type TrainingMatrixCourseOption = {
  course_key: string
  display_name: string
}

export function createTrainingMatrixApi(api: AxiosInstance) {
  return {
    uploadImport: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api
        .post<TrainingMatrixImport>('/api/v1/training-matrix/imports', form)
        .then((r) => r.data)
    },
    getLatestImport: () =>
      api.get<TrainingMatrixImport>('/api/v1/training-matrix/imports/latest').then((r) => r.data),
    getLatestImportQa: () =>
      api
        .get<TrainingMatrixImportQa>('/api/v1/training-matrix/imports/latest/qa')
        .then((r) => r.data),
    listCompliance: (params?: { status?: string; department?: string }) =>
      api
        .get<{ items: TrainingMatrixComplianceRow[]; total: number; atlas_hub_url: string }>(
          '/api/v1/training-matrix/compliance',
          { params },
        )
        .then((r) => r.data),
    myTraining: () =>
      api
        .get<{ items: TrainingMatrixComplianceRow[]; total: number; atlas_hub_url: string }>(
          '/api/v1/training-matrix/me',
        )
        .then((r) => r.data),
    listNameMaps: () =>
      api
        .get<TrainingMatrixNameMapItem[]>('/api/v1/training-matrix/name-maps')
        .then((r) => r.data),
    upsertNameMap: (atlas_name: string, engineer_id: number) =>
      api
        .put<TrainingMatrixNameMapItem>('/api/v1/training-matrix/name-maps', {
          atlas_name,
          engineer_id,
        })
        .then((r) => r.data),
    listRequirements: () =>
      api
        .get<{ items: TrainingMatrixRequirement[]; total: number }>(
          '/api/v1/training-matrix/requirements',
        )
        .then((r) => r.data),
    createRequirement: (body: Omit<TrainingMatrixRequirement, 'id'>) =>
      api
        .post<TrainingMatrixRequirement>('/api/v1/training-matrix/requirements', body)
        .then((r) => r.data),
    updateRequirement: (
      id: number,
      body: Partial<
        Pick<
          TrainingMatrixRequirement,
          | 'match_department'
          | 'match_role_key'
          | 'course_display_name'
          | 'frequency_years'
          | 'is_active'
          | 'notes'
        >
      >,
    ) =>
      api
        .patch<TrainingMatrixRequirement>(`/api/v1/training-matrix/requirements/${id}`, body)
        .then((r) => r.data),
    deleteRequirement: (id: number) =>
      api.delete(`/api/v1/training-matrix/requirements/${id}`).then(() => undefined),
    seedRequirements: (body?: { template?: string; mode?: 'fill_missing' | 'refresh_template' }) =>
      api
        .post<{
          template_id: string
          template_label: string
          created: number
          skipped_existing: number
          unmatched_modules: string[]
          created_without_atlas_match: number
        }>('/api/v1/training-matrix/requirements/seed', {
          template: body?.template ?? 'plantexpand_2024_v1',
          mode: body?.mode ?? 'fill_missing',
        })
        .then((r) => r.data),
    listCourses: () =>
      api
        .get<TrainingMatrixCourseOption[]>('/api/v1/training-matrix/courses')
        .then((r) => r.data),
  }
}
