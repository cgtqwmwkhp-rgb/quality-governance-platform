import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PortalLayout from '../../../src/components/PortalLayout';

vi.mock('../../../src/contexts/PortalAuthContext', () => ({
  usePortalAuth: vi.fn(() => ({ isAuthenticated: false, isLoading: true })),
}));

describe('PortalLayout', () => {
  it('shows loading state when isLoading is true', () => {
    render(
      <MemoryRouter>
        <PortalLayout />
      </MemoryRouter>
    );

    expect(screen.getByText('Loading...')).toBeTruthy();
  });

  it('renders null when not authenticated and not loading', async () => {
    const { usePortalAuth } = await import('../../../src/contexts/PortalAuthContext');
    (usePortalAuth as ReturnType<typeof vi.fn>).mockReturnValue({ isAuthenticated: false, isLoading: false });

    const { container } = render(
      <MemoryRouter>
        <PortalLayout />
      </MemoryRouter>
    );

    expect(container.innerHTML).toBe('');
  });
});
