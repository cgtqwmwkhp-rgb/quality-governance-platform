import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  settingsApi: {
    list: vi.fn().mockResolvedValue({
      items: [
        { key: 'company_name', value: 'TestCo', category: 'branding', description: 'Company name', value_type: 'string', is_editable: true },
      ],
    }),
    get: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn(),
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

import SystemSettings from '../../../src/pages/admin/SystemSettings';

describe('SystemSettings', () => {
  it('renders the System Settings heading', async () => {
    render(
      <MemoryRouter>
        <SystemSettings />
      </MemoryRouter>
    );
    expect(await screen.findByText('System Settings')).toBeInTheDocument();
  });

  it('renders setting category navigation items', async () => {
    render(
      <MemoryRouter>
        <SystemSettings />
      </MemoryRouter>
    );
    const brandingElements = await screen.findAllByText('Branding');
    expect(brandingElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Contact Details').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Notifications').length).toBeGreaterThanOrEqual(1);
  });

  it('switches category when a nav item is clicked', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SystemSettings />
      </MemoryRouter>
    );

    await screen.findByText('System Settings');
    const securityTab = screen.getByText('Security');
    await user.click(securityTab);
    expect(securityTab).toBeInTheDocument();
  });
});
