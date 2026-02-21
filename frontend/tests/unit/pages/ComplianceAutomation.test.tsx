import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
  it('renders the heading', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(await screen.findByText('Compliance Automation')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(
      await screen.findByText('Monitor regulations, track certificates, and automate compliance')
    ).toBeInTheDocument();
  });

  it('renders the Refresh button', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(await screen.findByText('Refresh')).toBeInTheDocument();
  });

  it('renders the overall compliance score', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(await screen.findByText('85.0%')).toBeInTheDocument();
    expect(screen.getByText('Overall Compliance Score')).toBeInTheDocument();
  });

  it('renders tab navigation with all tabs', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(await screen.findByText('Certificates')).toBeInTheDocument();
    expect(screen.getByText('Scheduled Audits')).toBeInTheDocument();
    expect(screen.getByText('Compliance Score')).toBeInTheDocument();
    expect(screen.getByText('RIDDOR')).toBeInTheDocument();
  });

  it('shows empty state for regulatory updates', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>
    );
    expect(await screen.findByText('All caught up')).toBeInTheDocument();
    expect(
      screen.getByText('No regulatory updates require your attention.')
    ).toBeInTheDocument();
  });
});
