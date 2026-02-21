import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  aiApi: {
    getPredictions: vi.fn().mockResolvedValue({ data: [] }),
    getAnomalies: vi.fn().mockResolvedValue({ data: [] }),
    getRecommendations: vi.fn().mockResolvedValue({ data: [] }),
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

import AIIntelligence from '../../../src/pages/AIIntelligence';

describe('AIIntelligence', () => {
  it('renders the heading', async () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(await screen.findByText('AI Intelligence Hub')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(
      await screen.findByText('Predictive Analytics & Smart Recommendations')
    ).toBeInTheDocument();
  });

  it('renders Run Analysis button', async () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Run Analysis')).toBeInTheDocument();
  });

  it('renders status cards', async () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Anomalies Detected')).toBeInTheDocument();
    expect(screen.getByText('Incident Clusters')).toBeInTheDocument();
    expect(screen.getByText('Recommendations')).toBeInTheDocument();
  });

  it('renders tab navigation buttons', async () => {
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Anomaly Detection')).toBeInTheDocument();
    expect(screen.getByText('AI Audit Assistant')).toBeInTheDocument();
    expect(screen.getByText('Smart Recommendations')).toBeInTheDocument();
  });

  it('switches to Audit Assistant tab and shows audit questions', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AIIntelligence />
      </MemoryRouter>
    );
    const auditTab = await screen.findByText('AI Audit Assistant');
    await user.click(auditTab);
    expect(await screen.findByText('AI-Generated Audit Questions')).toBeInTheDocument();
    expect(screen.getByText('Finding Trends')).toBeInTheDocument();
    expect(screen.getByText('Evidence Gap Analysis')).toBeInTheDocument();
  });
});
