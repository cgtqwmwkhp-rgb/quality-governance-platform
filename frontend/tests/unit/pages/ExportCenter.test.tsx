import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getExportJobs: vi.fn().mockResolvedValue({ data: [] }),
    createExportJob: vi.fn(),
    deleteExportJob: vi.fn(),
    downloadExport: vi.fn(),
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

import ExportCenter from '../../../src/pages/ExportCenter';

describe('ExportCenter', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
