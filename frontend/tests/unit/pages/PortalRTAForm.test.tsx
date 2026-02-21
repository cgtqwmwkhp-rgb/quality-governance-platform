import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    isAuthenticated: false,
    user: null,
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
  }),
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

vi.mock('../../../src/components/FuzzySearchDropdown', () => ({
  default: ({ label, placeholder }: { label: string; placeholder: string }) => (
    <div data-testid="fuzzy-search">
      <label>{label}</label>
      <input placeholder={placeholder} />
    </div>
  ),
}));

import PortalRTAForm from '../../../src/pages/PortalRTAForm';

describe('PortalRTAForm', () => {
  it('renders step 1 heading and progress indicator', () => {
    render(
      <MemoryRouter>
        <PortalRTAForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Details')).toBeInTheDocument();
    expect(screen.getByText('Driver and vehicle information')).toBeInTheDocument();
    expect(screen.getByText('RTA Report')).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument();
  });

  it('renders the Your Name input field', () => {
    render(
      <MemoryRouter>
        <PortalRTAForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Name *')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Full name...')).toBeInTheDocument();
  });

  it('renders the passenger question with Yes/No options', () => {
    render(
      <MemoryRouter>
        <PortalRTAForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Any passengers? *')).toBeInTheDocument();
    const yesButtons = screen.getAllByText('Yes');
    const noButtons = screen.getAllByText('No');
    expect(yesButtons.length).toBeGreaterThanOrEqual(1);
    expect(noButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the Continue button on step 1', () => {
    render(
      <MemoryRouter>
        <PortalRTAForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Continue')).toBeInTheDocument();
  });

  it('allows typing a name into the Your Name field', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PortalRTAForm />
      </MemoryRouter>
    );
    const nameInput = screen.getByPlaceholderText('Full name...');
    await user.type(nameInput, 'Jane Driver');
    expect(nameInput).toHaveValue('Jane Driver');
  });
});
