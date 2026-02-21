import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { investigationsApi, actionsApi } from "@/api/client";
import type { CreateFromRecordRequest, ActionCreate } from "@/api/client";

export function useInvestigations(params?: { page?: number; size?: number }) {
  const page = params?.page ?? 1;
  const size = params?.size ?? 50;
  return useQuery({
    queryKey: ["investigations", { page, size }],
    queryFn: () => investigationsApi.list(page, size).then((r) => r.data),
  });
}

export function useInvestigation(id: number) {
  return useQuery({
    queryKey: ["investigations", id],
    queryFn: () => investigationsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateInvestigationFromRecord() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateFromRecordRequest) =>
      investigationsApi.createFromRecord(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function useInvestigationActions(investigationId: number | null) {
  return useQuery({
    queryKey: ["actions", "investigation", investigationId],
    queryFn: () =>
      actionsApi
        .list(1, 50, undefined, "investigation", investigationId!)
        .then((r) => r.data.items || []),
    enabled: !!investigationId,
  });
}

export function useCreateInvestigationAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ActionCreate) =>
      actionsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
  });
}
