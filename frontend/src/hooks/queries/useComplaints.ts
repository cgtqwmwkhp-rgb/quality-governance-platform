import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { complaintsApi } from "@/api/client";
import type { ComplaintCreate } from "@/api/client";

export function useComplaints(params?: { page?: number; size?: number }) {
  const page = params?.page ?? 1;
  const size = params?.size ?? 50;
  return useQuery({
    queryKey: ["complaints", { page, size }],
    queryFn: () => complaintsApi.list(page, size).then((r) => r.data),
  });
}

export function useComplaint(id: number) {
  return useQuery({
    queryKey: ["complaints", id],
    queryFn: () => complaintsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateComplaint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ComplaintCreate) =>
      complaintsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["complaints"] });
    },
  });
}
