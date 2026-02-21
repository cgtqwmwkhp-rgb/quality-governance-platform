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

vi.mock('../../../src/hooks/useGeolocation', () => ({
  useGeolocation: () => ({
    latitude: null,
    longitude: null,
    accuracy: null,
    isLoading: false,
    error: null,
    formattedAddress: null,
    getLocation: vi.fn(),
    getLocationString: vi.fn(),
    clearError: vi.fn(),
  }),
}));

vi.mock('../../../src/hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({
    isListening: false,
    isSupported: false,
    transcript: '',
    startListening: vi.fn(),
    stopListening: vi.fn(),
    toggleListening: vi.fn(),
    error: null,
  }),
}));

vi.mock('../../../src/components/FuzzySearchDropdown', () => ({
  default: ({ label, placeholder }: { label: string; placeholder: string }) => (
    <div data-testid="fuzzy-search">
      <label>{label}</label>
      <input placeholder={placeholder} />
    </div>
  ),
}));

import PortalNearMissForm from '../../../src/pages/PortalNearMissForm';

describe('PortalNearMissForm', () => {
  it('renders step 1 heading and progress indicator', () => {
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Details')).toBeInTheDocument();
    expect(screen.getByText('Who is reporting this near miss?')).toBeInTheDocument();
    expect(screen.getByText('Near Miss Report')).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument();
  });

  it('renders the Your Name input field', () => {
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Name *')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Full name...')).toBeInTheDocument();
  });

  it('renders role selection buttons', () => {
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Role *')).toBeInTheDocument();
    expect(screen.getByText('Driver')).toBeInTheDocument();
    expect(screen.getByText('Technician')).toBeInTheDocument();
    expect(screen.getByText('Engineer')).toBeInTheDocument();
    expect(screen.getByText('Supervisor')).toBeInTheDocument();
  });

  it('renders the involvement question with Yes/No options', () => {
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Were you involved?')).toBeInTheDocument();
    expect(screen.getByText('Yes, I was involved')).toBeInTheDocument();
    expect(screen.getByText('No, I witnessed it')).toBeInTheDocument();
  });

  it('allows typing a name into the Your Name field', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    const nameInput = screen.getByPlaceholderText('Full name...');
    await user.type(nameInput, 'Bob Engineer');
    expect(nameInput).toHaveValue('Bob Engineer');
  });

  it('renders the Continue button on step 1', () => {
    render(
      <MemoryRouter>
        <PortalNearMissForm />
      </MemoryRouter>
    );
    expect(screen.getByText('Continue')).toBeInTheDocument();
  });
});
