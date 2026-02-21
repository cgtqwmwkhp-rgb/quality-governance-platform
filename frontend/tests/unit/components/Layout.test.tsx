import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../../../src/components/Layout';

vi.mock('../../../src/components/copilot/AICopilot', () => ({
  default: () => <div data-testid="ai-copilot" />,
}));

vi.mock('../../../src/components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <button data-testid="theme-toggle" />,
}));

describe('Layout', () => {
  it('renders the QGP logo text', () => {
    render(
      <MemoryRouter>
        <Layout onLogout={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('QGP')).toBeTruthy();
  });

  it('renders the platform name', () => {
    render(
      <MemoryRouter>
        <Layout onLogout={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('Quality Governance Platform')).toBeTruthy();
  });

  it('renders navigation items', () => {
    render(
      <MemoryRouter>
        <Layout onLogout={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('Incidents')).toBeTruthy();
    expect(screen.getByText('RTAs')).toBeTruthy();
  });

  it('renders the Sign Out button', () => {
    render(
      <MemoryRouter>
        <Layout onLogout={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('Sign Out')).toBeTruthy();
  });

  it('renders skip to content link', () => {
    render(
      <MemoryRouter>
        <Layout onLogout={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('Skip to main content')).toBeTruthy();
  });
});
