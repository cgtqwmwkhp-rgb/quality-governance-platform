import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  complianceApi: {
    getEvidenceLinks: vi.fn().mockResolvedValue({ data: [] }),
    autoTagRecord: vi.fn(),
    linkEvidence: vi.fn(),
    unlinkEvidence: vi.fn(),
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

import ComplianceEvidence from '../../../src/pages/ComplianceEvidence';

describe('ComplianceEvidence', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
