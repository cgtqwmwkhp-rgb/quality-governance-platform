import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getDashboards: vi.fn().mockResolvedValue({ data: [] }),
    getDashboard: vi.fn().mockResolvedValue({ data: { id: 1, name: 'Test', widgets: [] } }),
    createDashboard: vi.fn(),
    updateDashboard: vi.fn(),
    deleteDashboard: vi.fn(),
  },
}));

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

import DashboardBuilder from '../../../src/pages/DashboardBuilder';

describe('DashboardBuilder', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <DashboardBuilder />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
