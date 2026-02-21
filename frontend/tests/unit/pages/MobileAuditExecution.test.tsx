import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  auditsApi: {
    getRun: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        template_id: 1,
        location: 'Test Site',
        asset_id: 'ASSET-001',
        status: 'scheduled',
        responses: [],
      },
    }),
    getTemplate: vi.fn().mockResolvedValue({
      data: { name: 'Mobile Test Template', sections: [] },
    }),
    completeRun: vi.fn().mockResolvedValue({}),
    updateRun: vi.fn().mockResolvedValue({}),
    createResponse: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    updateResponse: vi.fn().mockResolvedValue({}),
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

import MobileAuditExecution from '../../../src/pages/MobileAuditExecution';

describe('MobileAuditExecution', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter initialEntries={['/audits/mobile/1']}>
        <MobileAuditExecution />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
