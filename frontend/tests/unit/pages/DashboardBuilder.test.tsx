import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    listDashboards: vi.fn().mockResolvedValue({ data: { dashboards: [] } }),
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
  it('renders the default dashboard name', async () => {
    render(
      <MemoryRouter>
        <DashboardBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('My Custom Dashboard')).toBeInTheDocument();
  });

  it('renders the Add Widget button', async () => {
    render(
      <MemoryRouter>
        <DashboardBuilder />
      </MemoryRouter>
    );
    await screen.findByText('My Custom Dashboard');
    expect(screen.getByText('Add Widget')).toBeInTheDocument();
  });

  it('renders the Save button', async () => {
    render(
      <MemoryRouter>
        <DashboardBuilder />
      </MemoryRouter>
    );
    await screen.findByText('My Custom Dashboard');
    expect(screen.getByText('Save')).toBeInTheDocument();
  });

  it('opens widget picker when Add Widget is clicked', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <DashboardBuilder />
      </MemoryRouter>
    );
    await screen.findByText('My Custom Dashboard');
    await user.click(screen.getByText('Add Widget'));
    expect(screen.getByText('KPI Card')).toBeInTheDocument();
  });
});
