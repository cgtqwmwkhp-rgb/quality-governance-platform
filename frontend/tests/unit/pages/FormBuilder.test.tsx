import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  formTemplatesApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 1, name: 'Test', fields: [], form_type: 'incident' } }),
    update: vi.fn(),
    create: vi.fn(),
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

import FormBuilder from '../../../src/pages/admin/FormBuilder';

describe('FormBuilder', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
