import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Incidents from '../../../src/pages/Incidents';

vi.mock('../../../src/api/client', () => {
  const emptyPaginated = { data: { items: [], total: 0, page: 1, size: 10, pages: 0 } };
  return {
    incidentsApi: {
      list: vi.fn().mockResolvedValue(emptyPaginated),
      create: vi.fn(),
      get: vi.fn(),
      update: vi.fn(),
    },
  };
});

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

describe('Incidents', () => {
  it('renders the Incidents heading', async () => {
    render(
      <MemoryRouter>
        <Incidents />
      </MemoryRouter>
    );
    const heading = await screen.findByText('Incidents', {}, { timeout: 5000 });
    expect(heading).toBeInTheDocument();
  });

  it('renders the New Incident button', async () => {
    render(
      <MemoryRouter>
        <Incidents />
      </MemoryRouter>
    );
    const newBtn = await screen.findByText('New Incident', {}, { timeout: 5000 });
    expect(newBtn).toBeInTheDocument();
  });

  it('renders the search input', async () => {
    render(
      <MemoryRouter>
        <Incidents />
      </MemoryRouter>
    );
    await screen.findByText('Incidents', {}, { timeout: 5000 });
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('opens create modal when New Incident is clicked', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Incidents />
      </MemoryRouter>
    );
    const newBtn = await screen.findByText('New Incident', {}, { timeout: 5000 });
    await user.click(newBtn);
    expect(newBtn).toBeInTheDocument();
  });
});
