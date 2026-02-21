import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  complianceAutomationApi: {
    listRegulatoryUpdates: vi.fn().mockResolvedValue({ data: { updates: [] } }),
    listCertificates: vi.fn().mockResolvedValue({ data: { certificates: [] } }),
    listScheduledAudits: vi.fn().mockResolvedValue({ data: { audits: [] } }),
    getComplianceScore: vi.fn().mockResolvedValue({
      data: { overall_score: 85, previous_score: 80, change: 5, breakdown: {} },
    }),
    listGapAnalyses: vi.fn().mockResolvedValue({ data: { analyses: [] } }),
    listRiddorSubmissions: vi.fn().mockResolvedValue({ data: { submissions: [] } }),
    getExpiringCertificates: vi.fn().mockResolvedValue({
      data: { expired: 0, expiring_7_days: 0, expiring_30_days: 0, expiring_90_days: 0, total_critical: 0 },
    }),
    reviewUpdate: vi.fn().mockResolvedValue({}),
    runGapAnalysis: vi.fn().mockResolvedValue({}),
    addCertificate: vi.fn().mockResolvedValue({}),
    scheduleAudit: vi.fn().mockResolvedValue({}),
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

import ComplianceAutomation from '../../../src/pages/ComplianceAutomation';

describe('ComplianceAutomation', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
