import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
  validateEnvironmentMatch: vi.fn().mockResolvedValue(null),
  getExpectedEnvironment: vi.fn(() => 'development'),
  getApiBaseUrl: vi.fn(() => 'https://test-api.example.com'),
}));

import { EnvironmentMismatchGuard } from '../../../src/components/EnvironmentMismatchGuard';

describe('EnvironmentMismatchGuard', () => {
  it('renders children when environments match', async () => {
    render(
      <EnvironmentMismatchGuard>
        <div>Protected Content</div>
      </EnvironmentMismatchGuard>
    );
    expect(await screen.findByText('Protected Content')).toBeInTheDocument();
  });

  it('shows warning when environment mismatch is detected', async () => {
    const { validateEnvironmentMatch } = await import('../../../src/config/apiBase');
    vi.mocked(validateEnvironmentMatch).mockResolvedValueOnce('Frontend and API environments do not match');

    render(
      <EnvironmentMismatchGuard>
        <div>Should Not Show</div>
      </EnvironmentMismatchGuard>
    );

    expect(await screen.findByText('Environment Mismatch Detected')).toBeInTheDocument();
    expect(screen.getByText(/Frontend and API environments do not match/)).toBeInTheDocument();
  });

  it('renders Retry and Continue Anyway buttons on mismatch', async () => {
    const { validateEnvironmentMatch } = await import('../../../src/config/apiBase');
    vi.mocked(validateEnvironmentMatch).mockResolvedValueOnce('Mismatch error');

    render(
      <EnvironmentMismatchGuard>
        <div>Content</div>
      </EnvironmentMismatchGuard>
    );

    expect(await screen.findByText('Retry')).toBeInTheDocument();
    expect(screen.getByText('Continue Anyway (Risky)')).toBeInTheDocument();
  });
});
