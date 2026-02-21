import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { rtasApi } from "@/api/client";
import type { RTACreate } from "@/api/client";

export function useRTAs(params?: { page?: number; size?: number }) {
  const page = params?.page ?? 1;
  const size = params?.size ?? 50;
  return useQuery({
    queryKey: ["rtas", { page, size }],
    queryFn: () => rtasApi.list(page, size).then((r) => r.data),
  });
}

export function useRTA(id: number) {
  return useQuery({
    queryKey: ["rtas", id],
    queryFn: () => rtasApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateRTA() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RTACreate) => rtasApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rtas"] });
    },
  });
}
