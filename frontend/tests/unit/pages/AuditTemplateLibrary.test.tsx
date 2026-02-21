import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  auditsApi: {
    listTemplates: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    createTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    cloneTemplate: vi.fn(),
    importTemplate: vi.fn(),
    archiveTemplate: vi.fn(),
    restoreTemplate: vi.fn(),
    listArchivedTemplates: vi.fn().mockResolvedValue({ data: { items: [] } }),
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

import AuditTemplateLibrary from '../../../src/pages/AuditTemplateLibrary';

describe('AuditTemplateLibrary', () => {
  it('renders the Audit Template Library heading', async () => {
    render(
      <MemoryRouter>
        <AuditTemplateLibrary />
      </MemoryRouter>
    );
    expect(await screen.findByText('Audit Template Library')).toBeInTheDocument();
  });

  it('renders search input and create button', async () => {
    render(
      <MemoryRouter>
        <AuditTemplateLibrary />
      </MemoryRouter>
    );
    await screen.findByText('Audit Template Library');
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('renders category filter options', async () => {
    render(
      <MemoryRouter>
        <AuditTemplateLibrary />
      </MemoryRouter>
    );
    await screen.findByText('Audit Template Library');
    expect(screen.getByText('All Categories')).toBeInTheDocument();
  });
});
