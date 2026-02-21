import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  contractsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    create: vi.fn(),
    update: vi.fn(),
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

import ContractsManagement from '../../../src/pages/admin/ContractsManagement';

describe('ContractsManagement', () => {
  it('renders the page heading', async () => {
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    expect(await screen.findByText('Contracts')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    expect(await screen.findByText('Manage contracts available in forms and reports')).toBeInTheDocument();
  });

  it('renders the Add Contract button', async () => {
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    const buttons = await screen.findAllByText('Add Contract');
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state when no contracts exist', async () => {
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    expect(await screen.findByText('No contracts found')).toBeInTheDocument();
    expect(screen.getByText('Add your first contract to get started')).toBeInTheDocument();
  });

  it('shows the contract details panel', async () => {
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    expect(await screen.findByText('Contract Details')).toBeInTheDocument();
    expect(screen.getByText('Select a contract to edit')).toBeInTheDocument();
  });

  it('shows the Add Contract form when clicking Add Contract', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ContractsManagement />
      </MemoryRouter>
    );
    const buttons = await screen.findAllByText('Add Contract');
    await user.click(buttons[0]);
    expect(screen.getByText('Name *')).toBeInTheDocument();
    expect(screen.getByText('Code *')).toBeInTheDocument();
    expect(screen.getByText('Client Name')).toBeInTheDocument();
  });
});
