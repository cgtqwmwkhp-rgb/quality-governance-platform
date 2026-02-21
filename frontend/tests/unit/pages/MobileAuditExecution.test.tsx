import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

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
      data: {
        name: 'Vehicle Inspection',
        sections: [
          {
            id: 1,
            title: 'Pre-Start Checks',
            questions: [
              {
                id: 101,
                text: 'Are tire pressures within acceptable range?',
                type: 'yes_no',
                is_required: true,
                weight: 1,
                evidence_required: false,
              },
              {
                id: 102,
                text: 'Are all lights functioning correctly?',
                type: 'yes_no',
                is_required: true,
                weight: 1,
                evidence_required: false,
              },
            ],
          },
        ],
      },
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

const renderWithRoute = () => {
  render(
    <MemoryRouter initialEntries={['/audits/mobile/1']}>
      <Routes>
        <Route path="/audits/mobile/:runId" element={<MobileAuditExecution />} />
      </Routes>
    </MemoryRouter>
  );
};

describe('MobileAuditExecution', () => {
  it('renders the template name after loading', async () => {
    renderWithRoute();
    expect(await screen.findByText('Vehicle Inspection')).toBeInTheDocument();
  });

  it('renders the asset identifier', async () => {
    renderWithRoute();
    expect(await screen.findByText('ASSET-001')).toBeInTheDocument();
  });

  it('renders the current question text', async () => {
    renderWithRoute();
    expect(
      await screen.findByText('Are tire pressures within acceptable range?')
    ).toBeInTheDocument();
  });

  it('renders YES and NO response buttons', async () => {
    renderWithRoute();
    expect(await screen.findByText('YES')).toBeInTheDocument();
    expect(screen.getByText('NO')).toBeInTheDocument();
  });

  it('renders navigation footer with Prev and Next buttons', async () => {
    renderWithRoute();
    expect(await screen.findByText('Prev')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
  });

  it('renders the Notes section', async () => {
    renderWithRoute();
    expect(await screen.findByText('Notes')).toBeInTheDocument();
  });
});
