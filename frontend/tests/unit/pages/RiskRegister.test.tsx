import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import RiskRegister from "../../../src/pages/RiskRegister";

vi.mock("../../../src/api/client", () => {
  const emptyPaginated = {
    data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
  };
  return {
    riskRegisterApi: {
      list: vi.fn().mockResolvedValue(emptyPaginated),
      getHeatmap: vi.fn().mockResolvedValue({
        data: {
          cells: [],
          matrix: [],
          summary: {
            total_risks: 0,
            critical_risks: 0,
            high_risks: 0,
            outside_appetite: 0,
            average_inherent_score: 0,
            average_residual_score: 0,
          },
          likelihood_labels: {},
          impact_labels: {},
        },
      }),
      getSummary: vi.fn().mockResolvedValue({
        data: {
          total_risks: 0,
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
          by_category: {},
        },
      }),
      getTrends: vi.fn().mockResolvedValue({ data: {} }),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      assess: vi.fn(),
      get: vi.fn(),
      getBowtie: vi.fn().mockResolvedValue({ data: {} }),
      addBowtieElement: vi.fn(),
      deleteBowtieElement: vi.fn(),
      listControls: vi.fn().mockResolvedValue({ data: [] }),
      createControl: vi.fn(),
      linkControl: vi.fn(),
      getKRIDashboard: vi.fn().mockResolvedValue({ data: {} }),
      createKRI: vi.fn(),
      updateKRIValue: vi.fn(),
      getKRIHistory: vi.fn().mockResolvedValue({ data: {} }),
      getAppetiteStatements: vi.fn().mockResolvedValue({ data: [] }),
    },
    usersApi: {
      search: vi.fn().mockResolvedValue({ data: [] }),
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

describe("RiskRegister", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it("renders the Enterprise Risk Register heading", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RiskRegister />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText(
        "Enterprise Risk Register",
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
  });

  it("renders the Add Risk button", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RiskRegister />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText("Add Risk", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("renders the Heat Map view toggle", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RiskRegister />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("Enterprise Risk Register", {}, { timeout: 5000 });
    expect(screen.getByText(/Heat Map/i)).toBeInTheDocument();
  });

  it("opens Add Risk dialog when button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RiskRegister />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const addBtn = await screen.findByText("Add Risk", {}, { timeout: 5000 });
    await user.click(addBtn);
    expect(screen.getByText(/Add New Risk/i)).toBeInTheDocument();
  });
});
