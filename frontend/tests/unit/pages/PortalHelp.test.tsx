import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

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

import PortalHelp from '../../../src/pages/PortalHelp';

describe('PortalHelp', () => {
  it('renders the Help & Support header', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('Help & Support')).toBeInTheDocument();
  });

  it('renders the hero heading', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('How can we help?')).toBeInTheDocument();
    expect(screen.getByText('Search our knowledge base or browse by category')).toBeInTheDocument();
  });

  it('renders the search input', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByPlaceholderText('Search for answers...')).toBeInTheDocument();
  });

  it('renders category cards', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('Reporting Issues')).toBeInTheDocument();
    expect(screen.getByText('Anonymous Reports')).toBeInTheDocument();
    expect(screen.getByText('Tracking Status')).toBeInTheDocument();
    expect(screen.getByText('Emergencies')).toBeInTheDocument();
  });

  it('renders FAQ questions', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('Frequently Asked Questions')).toBeInTheDocument();
    expect(screen.getByText('How do I submit a report?')).toBeInTheDocument();
    expect(screen.getByText('What counts as an emergency?')).toBeInTheDocument();
  });

  it('renders the contact section', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('Still need help?')).toBeInTheDocument();
    expect(screen.getByText('Live Chat')).toBeInTheDocument();
    expect(screen.getByText('Email Support')).toBeInTheDocument();
    expect(screen.getByText('Call Helpline')).toBeInTheDocument();
  });

  it('renders quick action buttons', async () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    expect(await screen.findByText('Submit a Report')).toBeInTheDocument();
    expect(screen.getByText('Track My Report')).toBeInTheDocument();
  });

  it('filters FAQs when searching', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>
    );
    const searchInput = await screen.findByPlaceholderText('Search for answers...');
    await user.type(searchInput, 'emergency');
    expect(screen.getByText('Search Results')).toBeInTheDocument();
    expect(screen.getByText('What counts as an emergency?')).toBeInTheDocument();
  });
});
