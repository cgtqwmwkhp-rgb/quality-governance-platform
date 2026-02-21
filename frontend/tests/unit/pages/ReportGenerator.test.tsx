import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getReports: vi.fn().mockResolvedValue({ data: [] }),
    generateReport: vi.fn(),
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

import ReportGenerator from '../../../src/pages/ReportGenerator';

describe('ReportGenerator', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <ReportGenerator />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
