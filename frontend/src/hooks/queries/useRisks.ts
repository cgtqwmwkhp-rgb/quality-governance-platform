import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { riskRegisterApi } from "@/api/client";
import type { RiskEntry } from "@/api/client";

export function useRisks(params?: {
  skip?: number;
  limit?: number;
  status?: string;
  category?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: ["risks", params],
    queryFn: () => riskRegisterApi.list(params).then((r) => r.data),
  });
}

export function useRisk(id: number) {
  return useQuery({
    queryKey: ["risks", id],
    queryFn: () => riskRegisterApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useRiskHeatmap() {
  return useQuery({
    queryKey: ["risks", "heatmap"],
    queryFn: () => riskRegisterApi.getHeatmap().then((r) => r.data),
  });
}

export function useRiskSummary() {
  return useQuery({
    queryKey: ["risks", "summary"],
    queryFn: () => riskRegisterApi.getSummary().then((r) => r.data),
  });
}

export function useCreateRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<RiskEntry>) =>
      riskRegisterApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useUpdateRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<RiskEntry> }) =>
      riskRegisterApi.update(id, data).then((r) => r.data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["risks"] });
      queryClient.invalidateQueries({ queryKey: ["risks", variables.id] });
    },
  });
}

export function useDeleteRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => riskRegisterApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useAssessRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      scores,
    }: {
      id: number;
      scores: { likelihood: number; impact: number };
    }) => riskRegisterApi.assess(id, scores).then((r) => r.data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["risks"] });
      queryClient.invalidateQueries({ queryKey: ["risks", variables.id] });
    },
  });
}
