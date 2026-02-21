import { useQuery } from "@tanstack/react-query";
import {
  incidentsApi,
  rtasApi,
  complaintsApi,
  actionsApi,
  auditsApi,
  notificationsApi,
  executiveDashboardApi,
} from "@/api/client";

export function useDashboardData() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const [
        incidentsRes,
        rtasRes,
        complaintsRes,
        actionsRes,
        auditRunsRes,
        notifRes,
        execDashRes,
      ] = await Promise.allSettled([
        incidentsApi.list(1, 100),
        rtasApi.list(1, 100),
        complaintsApi.list(1, 100),
        actionsApi.list(1, 100),
        auditsApi.listRuns(1, 100),
        notificationsApi.getUnreadCount(),
        executiveDashboardApi.getDashboard(30),
      ]);

      return {
        incidents:
          incidentsRes.status === "fulfilled"
            ? incidentsRes.value.data.items || []
            : [],
        rtas:
          rtasRes.status === "fulfilled" ? rtasRes.value.data.items || [] : [],
        complaints:
          complaintsRes.status === "fulfilled"
            ? complaintsRes.value.data.items || []
            : [],
        actions:
          actionsRes.status === "fulfilled"
            ? actionsRes.value.data.items || []
            : [],
        auditRuns:
          auditRunsRes.status === "fulfilled"
            ? auditRunsRes.value.data.items || []
            : [],
        unreadCount:
          notifRes.status === "fulfilled"
            ? notifRes.value.data.unread_count || 0
            : 0,
        execDash:
          execDashRes.status === "fulfilled" ? execDashRes.value.data : null,
      };
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
