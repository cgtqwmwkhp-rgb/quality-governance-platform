import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  formTemplatesApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    create: vi.fn(),
    delete: vi.fn(),
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

import FormsList from '../../../src/pages/admin/FormsList';

describe('FormsList', () => {
  it('renders the Form Builder heading and subtitle', async () => {
    render(
      <MemoryRouter>
        <FormsList />
      </MemoryRouter>
    );
    expect(await screen.findByText('Form Builder')).toBeInTheDocument();
    expect(
      screen.getByText('Create and manage customizable forms for incidents, complaints, and more')
    ).toBeInTheDocument();
  });

  it('renders the Create New Form button', async () => {
    render(
      <MemoryRouter>
        <FormsList />
      </MemoryRouter>
    );
    const buttons = await screen.findAllByText('Create New Form');
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows the empty state when no forms are loaded', async () => {
    render(
      <MemoryRouter>
        <FormsList />
      </MemoryRouter>
    );
    expect(await screen.findByText('No forms found')).toBeInTheDocument();
    expect(screen.getByText('Get started by creating your first form')).toBeInTheDocument();
  });

  it('renders the search input', async () => {
    render(
      <MemoryRouter>
        <FormsList />
      </MemoryRouter>
    );
    expect(await screen.findByPlaceholderText('Search forms...')).toBeInTheDocument();
  });

  it('renders filter type buttons', async () => {
    render(
      <MemoryRouter>
        <FormsList />
      </MemoryRouter>
    );
    expect(await screen.findByText('All')).toBeInTheDocument();
    expect(screen.getByText('Incident')).toBeInTheDocument();
    expect(screen.getByText('Near Miss')).toBeInTheDocument();
    expect(screen.getByText('Complaint')).toBeInTheDocument();
    expect(screen.getByText('RTA')).toBeInTheDocument();
    expect(screen.getByText('Audit')).toBeInTheDocument();
  });
});
