import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
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
  default: () => <div>FuzzySearchDropdown</div>,
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

import PortalIncidentForm from '../../../src/pages/PortalIncidentForm';

describe('PortalIncidentForm', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <PortalIncidentForm />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
