import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  formTemplatesApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 1, name: 'Test', fields: [], form_type: 'incident' } }),
    getById: vi.fn().mockResolvedValue({ id: 1, name: 'Test', fields: [], form_type: 'incident', steps: [] }),
    update: vi.fn(),
    create: vi.fn(),
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

import FormBuilder from '../../../src/pages/admin/FormBuilder';

describe('FormBuilder', () => {
  it('renders the Create New Form heading', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('Create New Form')).toBeInTheDocument();
    expect(screen.getByText('Design your form with drag-and-drop fields')).toBeInTheDocument();
  });

  it('renders the Form Details section with inputs', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('Form Details')).toBeInTheDocument();
    expect(screen.getByText('Form Name *')).toBeInTheDocument();
    expect(screen.getByText('Form Type')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('e.g. Incident Report Form')).toBeInTheDocument();
  });

  it('renders Save Form, Settings, and Preview buttons', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('Save Form')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Preview')).toBeInTheDocument();
  });

  it('renders the Form Steps section with a default step', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('Form Steps')).toBeInTheDocument();
    expect(screen.getByText('Add Step')).toBeInTheDocument();
    expect(screen.getByText('No fields yet')).toBeInTheDocument();
    expect(screen.getByText('Add Field')).toBeInTheDocument();
  });

  it('renders the Form Settings sidebar', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/forms/new']}>
        <FormBuilder />
      </MemoryRouter>
    );
    expect(await screen.findByText('Form Settings')).toBeInTheDocument();
    expect(screen.getByText('Reference Prefix')).toBeInTheDocument();
    expect(screen.getByText('Allow Draft Saving')).toBeInTheDocument();
    expect(screen.getByText('Allow Attachments')).toBeInTheDocument();
    expect(screen.getByText('Require Signature')).toBeInTheDocument();
    expect(screen.getByText('Notify on Submit')).toBeInTheDocument();
  });
});
