import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { actionsApi } from "@/api/client";
import type { ActionCreate } from "@/api/client";

export function useActions(params?: {
  page?: number;
  size?: number;
  status?: string;
}) {
  const page = params?.page ?? 1;
  const size = params?.size ?? 100;
  return useQuery({
    queryKey: ["actions", { page, size, status: params?.status }],
    queryFn: () =>
      actionsApi.list(page, size, params?.status).then((r) => r.data),
  });
}

export function useCreateAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ActionCreate) =>
      actionsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
  });
}

export function useUpdateAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      sourceType,
      data,
    }: {
      id: number;
      sourceType: string;
      data: { status?: string; completion_notes?: string };
    }) => actionsApi.update(id, sourceType, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
  });
}
