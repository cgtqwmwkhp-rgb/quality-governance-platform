import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";

export function useDocuments(params?: { page?: number; pageSize?: number }) {
  const page = params?.page ?? 1;
  const pageSize = params?.pageSize ?? 50;
  return useQuery({
    queryKey: ["documents", { page, pageSize }],
    queryFn: () =>
      api
        .get(`/api/v1/documents?page=${page}&page_size=${pageSize}`)
        .then((r) => r.data),
  });
}

export function useDocumentStats() {
  return useQuery({
    queryKey: ["documents", "stats"],
    queryFn: () =>
      api.get("/api/v1/documents/stats/overview").then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useSemanticSearch(query: string) {
  return useQuery({
    queryKey: ["documents", "search", query],
    queryFn: () =>
      api
        .get(
          `/api/v1/documents/search/semantic?q=${encodeURIComponent(query)}&top_k=10`,
        )
        .then((r) => r.data.results),
    enabled: query.length >= 3,
  });
}
