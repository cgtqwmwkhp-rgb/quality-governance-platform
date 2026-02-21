import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  rtasApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 1, title: 'Test RTA', status: 'open', severity: 'low', description: '', location: '', vehicle_registration: '' } }),
    update: vi.fn(),
  },
  investigationsApi: { create: vi.fn() },
  actionsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }) },
  getApiErrorMessage: vi.fn(() => 'Error'),
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

import RTADetail from '../../../src/pages/RTADetail';

describe('RTADetail', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter initialEntries={['/rtas/1']}>
        <RTADetail />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
