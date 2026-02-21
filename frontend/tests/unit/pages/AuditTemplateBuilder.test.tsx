import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  auditsApi: {
    createTemplate: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    getTemplate: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        name: 'Test Template',
        description: '',
        version: 1,
        is_published: false,
        question_count: 0,
        sections: [],
        category: '',
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
  it('renders without crashing', () => {
    render(
      <MemoryRouter initialEntries={['/audit-templates/new']}>
        <AuditTemplateBuilder />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
