import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { incidentsApi } from "@/api/client";
import type { IncidentCreate, IncidentUpdate } from "@/api/client";

export function useIncidents(params?: { page?: number; size?: number }) {
  const page = params?.page ?? 1;
  const size = params?.size ?? 10;
  return useQuery({
    queryKey: ["incidents", { page, size }],
    queryFn: () => incidentsApi.list(page, size).then((r) => r.data),
  });
}

export function useIncident(id: number) {
  return useQuery({
    queryKey: ["incidents", id],
    queryFn: () => incidentsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: IncidentCreate) =>
      incidentsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
}

export function useUpdateIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: IncidentUpdate }) =>
      incidentsApi.update(id, data).then((r) => r.data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["incidents", variables.id] });
    },
  });
}
