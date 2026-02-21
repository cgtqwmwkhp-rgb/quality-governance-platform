import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  usersApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  auditTrailApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  actionsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
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

import AdminDashboard from '../../../src/pages/admin/AdminDashboard';

describe('AdminDashboard', () => {
  it('renders the heading after loading', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText('Admin Dashboard')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    expect(
      await screen.findByText('Manage forms, contracts, settings, and system configuration')
    ).toBeInTheDocument();
  });

  it('renders the System Healthy badge', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText('System Healthy')).toBeInTheDocument();
  });

  it('renders Quick Actions with action items', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText('Quick Actions')).toBeInTheDocument();
    expect(screen.getByText('Form Builder')).toBeInTheDocument();
    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('System Settings')).toBeInTheDocument();
    expect(screen.getByText('Lookup Tables')).toBeInTheDocument();
    expect(screen.getByText('Notifications')).toBeInTheDocument();
  });

  it('renders System Status section with services', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    const statusElements = await screen.findAllByText('System Status');
    expect(statusElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('API Server')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Authentication')).toBeInTheDocument();
    expect(screen.getByText('Background Jobs')).toBeInTheDocument();
  });
});
