import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { auditsApi } from '@/api/client'
import type { AuditRunCreate, AuditRunUpdate, AuditTemplateCreate } from '@/api/client'

export function useAuditTemplates(params?: {
  page?: number
  size?: number
  search?: string
  category?: string
  is_published?: boolean
}) {
  const page = params?.page ?? 1
  const size = params?.size ?? 20
  return useQuery({
    queryKey: ['audit-templates', { page, size, search: params?.search, category: params?.category, is_published: params?.is_published }],
    queryFn: () => auditsApi.listTemplates(page, size, {
      search: params?.search,
      category: params?.category,
      is_published: params?.is_published,
    }).then(r => r.data),
  })
}

export function useAuditTemplate(id: number) {
  return useQuery({
    queryKey: ['audit-templates', id],
    queryFn: () => auditsApi.getTemplate(id).then(r => r.data),
    enabled: !!id,
  })
}

export function useCreateAuditTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AuditTemplateCreate) =>
      auditsApi.createTemplate(data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-templates'] })
    },
  })
}

export function useAuditRuns(params?: { page?: number; size?: number }) {
  const page = params?.page ?? 1
  const size = params?.size ?? 10
  return useQuery({
    queryKey: ['audit-runs', { page, size }],
    queryFn: () => auditsApi.listRuns(page, size).then(r => r.data),
  })
}

export function useAuditRun(id: number) {
  return useQuery({
    queryKey: ['audit-runs', id],
    queryFn: () => auditsApi.getRun(id).then(r => r.data),
    enabled: !!id,
  })
}

export function useCreateAuditRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AuditRunCreate) =>
      auditsApi.createRun(data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-runs'] })
    },
  })
}

export function useUpdateAuditRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: AuditRunUpdate }) =>
      auditsApi.updateRun(id, data).then(r => r.data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['audit-runs'] })
      queryClient.invalidateQueries({ queryKey: ['audit-runs', variables.id] })
    },
  })
}

export function useAuditFindings(params?: { page?: number; size?: number; runId?: number }) {
  const page = params?.page ?? 1
  const size = params?.size ?? 10
  return useQuery({
    queryKey: ['audit-findings', { page, size, runId: params?.runId }],
    queryFn: () => auditsApi.listFindings(page, size, params?.runId).then(r => r.data),
  })
}
