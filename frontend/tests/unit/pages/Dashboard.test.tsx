import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../../../src/pages/Dashboard";

vi.mock("../../../src/api/client", () => {
  const emptyPaginated = {
    data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
  };
  return {
    incidentsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    rtasApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    complaintsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    actionsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    auditsApi: { listRuns: vi.fn().mockResolvedValue(emptyPaginated) },
    notificationsApi: {
      getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
    },
    executiveDashboardApi: {
      getDashboard: vi.fn().mockResolvedValue({
        data: {
          risks: { total_active: 0, high_critical: 0 },
          near_misses: { trend_percent: 0 },
          compliance: { completion_rate: 0 },
          kris: { at_risk: 0 },
        },
      }),
    },
  };
});

vi.mock("../../../src/config/apiBase", () => ({
  API_BASE_URL: "https://test-api.example.com",
}));

vi.mock("../../../src/stores/useAppStore", () => ({
  useAppStore: {
    getState: () => ({
      setLoading: vi.fn(),
      setConnectionStatus: vi.fn(),
    }),
  },
}));

vi.mock("../../../src/utils/auth", () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

describe("Dashboard", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it("renders the Dashboard heading", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const heading = await screen.findByText("Dashboard");
    expect(heading).toBeInTheDocument();
  });

  it("shows the subtitle text", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText("Quality Governance Platform Overview"),
    ).toBeInTheDocument();
  });

  it("renders the Refresh button", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const refreshBtn = await screen.findByText("Refresh");
    expect(refreshBtn).toBeInTheDocument();
  });

  it("renders stat cards after loading", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Open Incidents")).toBeInTheDocument();
    expect(screen.getByText("Open RTAs")).toBeInTheDocument();
    expect(screen.getByText("Open Complaints")).toBeInTheDocument();
    expect(screen.getByText("Overdue Actions")).toBeInTheDocument();
  });

  it("renders IMS Compliance section", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("IMS Compliance")).toBeInTheDocument();
  });

  it("renders quick action links", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("New Incident")).toBeInTheDocument();
    expect(screen.getByText("Start Audit")).toBeInTheDocument();
    expect(screen.getByText("View Analytics")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
  });

  it("renders quick action links as clickable elements", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const newIncident = await screen.findByText("New Incident");
    expect(newIncident.closest("a, button")).not.toBeNull();
  });
});
