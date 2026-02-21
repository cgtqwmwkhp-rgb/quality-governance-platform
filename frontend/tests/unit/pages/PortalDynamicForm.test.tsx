import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  formTemplatesApi: {
    getBySlug: vi.fn().mockResolvedValue({ data: null }),
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  contractsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  lookupsApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    isAuthenticated: false,
    user: null,
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock('../../../src/components/DynamicForm', () => ({
  DynamicFormRenderer: () => <div>DynamicForm</div>,
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

import PortalDynamicForm from '../../../src/pages/PortalDynamicForm';

describe('PortalDynamicForm', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
