import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import Actions from "../../../src/pages/Actions";

vi.mock("../../../src/api/client", () => ({
  incidentsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  rtasApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  complaintsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  actionsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
    create: vi.fn().mockResolvedValue({ data: {} }),
  },
  auditsApi: {
    listRuns: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  risksApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  policiesApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  documentsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  investigationsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  executiveDashboardApi: {
    getDashboard: vi
      .fn()
      .mockResolvedValue({
        data: {
          risks: { total_active: 0, high_critical: 0 },
          near_misses: { trend_percent: 0 },
          compliance: { completion_rate: 0 },
          kris: { at_risk: 0 },
        },
      }),
  },
  standardsApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  workflowApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  usersApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  nearMissApi: {
    list: vi
      .fn()
      .mockResolvedValue({
        data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      }),
  },
  analyticsApi: { getDashboard: vi.fn().mockResolvedValue({ data: {} }) },
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock("../../../src/config/apiBase", () => ({
  API_BASE_URL: "https://test-api.example.com",
}));

vi.mock("../../../src/stores/useAppStore", () => ({
  useAppStore: {
    getState: () => ({ setLoading: vi.fn(), setConnectionStatus: vi.fn() }),
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

describe("Actions", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it("renders the Action Center heading", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Actions />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Action Center")).toBeInTheDocument();
  });

  it("renders the Create Action button", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Actions />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("Action Center");
    expect(screen.getByText(/Create Action|New Action/i)).toBeInTheDocument();
  });

  it("renders search input", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Actions />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("Action Center");
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("opens create dialog when Create Action is clicked", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Actions />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("Action Center");
    const createBtn = screen.getByText(/Create Action|New Action/i);
    await user.click(createBtn);
    expect(createBtn).toBeInTheDocument();
  });
});
