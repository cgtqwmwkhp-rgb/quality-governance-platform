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

vi.mock('../../../src/components/FuzzySearchDropdown', () => ({
  default: ({ label }: { label: string }) => <div>{label}</div>,
}));

vi.mock('../../../src/components/BodyInjurySelector', () => ({
  default: () => <div>BodyInjurySelector</div>,
}));

vi.mock('../../../src/components/DraftRecoveryDialog', () => ({
  default: () => null,
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
  useGeolocation: () => ({ isLoading: false, getLocationString: vi.fn(), error: null }),
}));

vi.mock('../../../src/hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({ isListening: false, isSupported: false, toggleListening: vi.fn(), error: null }),
}));

vi.mock('../../../src/hooks/useFormAutosave', () => ({
  useFormAutosave: () => ({
    isRecoveryPromptOpen: false,
    draftData: null,
    lastSavedAt: null,
    saveDraft: vi.fn(),
    recoverDraft: vi.fn(),
    discardDraft: vi.fn(),
    clearDraft: vi.fn(),
  }),
}));

vi.mock('../../../src/hooks/useFeatureFlag', () => ({
  useFeatureFlag: () => false,
}));

vi.mock('../../../src/services/telemetry', () => ({
  trackExp001FormOpened: vi.fn(),
  trackExp001FormSubmitted: vi.fn(),
  trackExp001FormAbandoned: vi.fn(),
}));

import PortalIncidentForm from '../../../src/pages/PortalIncidentForm';

describe('PortalIncidentForm', () => {
  it('renders Step 1 with Contract Details heading', async () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('Contract Details')).toBeInTheDocument();
    expect(screen.getByText('Which contract does this relate to?')).toBeInTheDocument();
  });

  it('renders the Incident Report header', async () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('Incident Report')).toBeInTheDocument();
  });

  it('shows step progress indicator', async () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(await screen.findByText(/Step 1 of/)).toBeInTheDocument();
  });

  it('renders the Select Contract dropdown label', async () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('Select Contract')).toBeInTheDocument();
  });

  it('renders the Continue button on step 1', async () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('Continue')).toBeInTheDocument();
  });
});
