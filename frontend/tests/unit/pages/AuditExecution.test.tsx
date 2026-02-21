import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  auditsApi: {
    getRun: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        template_id: 1,
        location: 'Test Site',
        title: 'Test Audit Run',
        status: 'scheduled',
        responses: [],
      },
    }),
    getTemplate: vi.fn().mockResolvedValue({
      data: {
        name: 'Safety Inspection Template',
        sections: [
          {
            id: 1,
            title: 'General Safety',
            description: 'Basic safety checks',
            questions: [
              {
                id: 1,
                question_text: 'Are fire exits clear?',
                question_type: 'yes_no',
                is_required: true,
                weight: 1,
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

import AuditExecution from '../../../src/pages/AuditExecution';

describe('AuditExecution', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/audits/1/execute']}>
        <Routes>
          <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
        </Routes>
      </MemoryRouter>
    );

  it('renders the template name', async () => {
    renderPage();
    expect(await screen.findByText('Safety Inspection Template')).toBeInTheDocument();
  });

  it('renders the audit location', async () => {
    renderPage();
    await screen.findByText('Safety Inspection Template');
    expect(screen.getByText(/Test Site/)).toBeInTheDocument();
  });

  it('renders the first question', async () => {
    renderPage();
    expect(await screen.findByText('Are fire exits clear?')).toBeInTheDocument();
  });
});
