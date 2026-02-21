import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  formTemplatesApi: {
    getBySlug: vi.fn().mockResolvedValue(null),
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  contractsApi: {
    list: vi.fn().mockResolvedValue(null),
  },
  lookupsApi: {
    list: vi.fn().mockResolvedValue(null),
  },
}));

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

vi.mock('../../../src/components/DynamicForm', () => ({
  DynamicFormRenderer: ({ template }: { template: { name: string; steps: { name: string }[] } }) => (
    <div data-testid="dynamic-form">
      <div>DynamicFormRendered</div>
      <div data-testid="template-name">{template.name}</div>
      {template.steps.map((s: { name: string }, i: number) => (
        <div key={i}>{s.name}</div>
      ))}
    </div>
  ),
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

import PortalDynamicForm from '../../../src/pages/PortalDynamicForm';

describe('PortalDynamicForm', () => {
  it('renders the Incident Report header after loading', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    const headings = await screen.findAllByText('Incident Report');
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the DynamicFormRenderer component', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('DynamicFormRendered')).toBeInTheDocument();
    expect(screen.getByTestId('dynamic-form')).toBeInTheDocument();
  });

  it('shows the fallback template name in the renderer', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    const templateName = await screen.findByTestId('template-name');
    expect(templateName).toHaveTextContent('Incident Report');
  });

  it('shows fallback template step names for incident', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    expect(await screen.findByText('Contract Details')).toBeInTheDocument();
    expect(screen.getByText('People & Location')).toBeInTheDocument();
    expect(screen.getByText('What Happened')).toBeInTheDocument();
    expect(screen.getByText('Injuries & Evidence')).toBeInTheDocument();
  });

  it('renders the back navigation button', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    await screen.findByText('DynamicFormRendered');
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('displays version and step count info', async () => {
    render(
      <MemoryRouter>
        <PortalDynamicForm />
      </MemoryRouter>
    );
    await screen.findByText('DynamicFormRendered');
    expect(screen.getByText(/v1/)).toBeInTheDocument();
    expect(screen.getByText(/4 steps/)).toBeInTheDocument();
  });
});
