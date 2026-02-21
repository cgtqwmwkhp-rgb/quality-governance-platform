import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RiskRegister from '../../../src/pages/RiskRegister';

vi.mock('../../../src/api/client', () => {
  const emptyPaginated = { data: { items: [], total: 0, page: 1, size: 10, pages: 0 } };
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
        data: { total_risks: 0, critical: 0, high: 0, medium: 0, low: 0, by_category: {} },
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

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/stores/useAppStore', () => ({
  useAppStore: {
    getState: () => ({
      setLoading: vi.fn(),
      setConnectionStatus: vi.fn(),
    }),
  },
}));

vi.mock('../../../src/utils/auth', () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

describe('RiskRegister', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>
    );

    const heading = await screen.findByText('Enterprise Risk Register', {}, { timeout: 5000 });
    expect(heading).toBeTruthy();
  });

  it('renders the Add Risk button', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>
    );

    const addBtn = await screen.findByText('Add Risk', {}, { timeout: 5000 });
    expect(addBtn).toBeTruthy();
  });
});
