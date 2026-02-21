import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  auditsApi: {
    createTemplate: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    getTemplate: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        name: 'Test Template',
        description: 'A test template for audits',
        version: 1,
        is_published: false,
        question_count: 0,
        sections: [],
        category: 'quality',
        scoring_method: 'percentage',
        passing_score: 80,
        audit_type: 'inspection',
      },
    }),
    updateTemplate: vi.fn().mockResolvedValue({}),
    publishTemplate: vi.fn().mockResolvedValue({}),
    createSection: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    updateSection: vi.fn().mockResolvedValue({}),
    deleteSection: vi.fn().mockResolvedValue({}),
    createQuestion: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    updateQuestion: vi.fn().mockResolvedValue({}),
    deleteQuestion: vi.fn().mockResolvedValue({}),
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

vi.mock('../../../src/components/AITemplateGenerator', () => ({
  default: () => null,
}));

import AuditTemplateBuilder from '../../../src/pages/AuditTemplateBuilder';

describe('AuditTemplateBuilder', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/audit-templates/1']}>
        <Routes>
          <Route path="/audit-templates/:templateId" element={<AuditTemplateBuilder />} />
        </Routes>
      </MemoryRouter>
    );

  it('renders the template name in the input field', async () => {
    renderPage();
    expect(await screen.findByDisplayValue('Test Template')).toBeInTheDocument();
  });

  it('renders the Draft badge', async () => {
    renderPage();
    await screen.findByDisplayValue('Test Template');
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });

  it('renders Add Section button', async () => {
    renderPage();
    await screen.findByDisplayValue('Test Template');
    expect(screen.getByText(/Add Section/i)).toBeInTheDocument();
  });
});
