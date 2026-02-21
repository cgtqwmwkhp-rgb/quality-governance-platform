import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
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
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
