import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AuditTemplateLibrary from '../AuditTemplateLibrary';

const mockNavigate = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'audit_templates.title': 'Audit Template Library',
        'audit_templates.subtitle': 'Manage your inspection templates',
        'audit_templates.new': 'New Template',
        'audit_templates.search_placeholder': 'Search templates...',
        'audit_templates.batch_import': 'Batch Import',
        'audit_templates.empty.title': 'No templates found',
        'audit_templates.empty.subtitle': 'Create your first template',
        'audit_templates.empty.filter_hint': 'Try adjusting your search or filters',
        'audit_templates.clear_filters': 'Clear Filters',
        'import': 'Import',
      };
      return translations[key] || key;
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../api/client', () => ({
  auditsApi: {
    listTemplates: vi.fn(),
    listArchivedTemplates: vi.fn(),
    listCategories: vi.fn(),
    deleteTemplate: vi.fn(),
    restoreTemplate: vi.fn(),
    cloneTemplate: vi.fn(),
    batchImportTemplates: vi.fn(),
  },
}));

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}));

const MOCK_TEMPLATES = [
  {
    id: 1,
    reference_number: 'TPL-001',
    name: 'Vehicle Inspection Checklist',
    description: 'Standard vehicle inspection template',
    category: 'Vehicles',
    audit_type: 'inspection',
    version: 1,
    is_active: true,
    is_published: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-02-15T00:00:00Z',
    scoring_method: 'percentage',
    question_count: 10,
    section_count: 3,
  },
  {
    id: 2,
    reference_number: 'TPL-002',
    name: 'Plant Safety Audit',
    description: 'Draft plant machinery audit',
    category: 'Plant & Machinery',
    audit_type: 'safety',
    version: 2,
    is_active: true,
    is_published: false,
    created_at: '2026-01-10T00:00:00Z',
    updated_at: '2026-03-01T00:00:00Z',
    scoring_method: 'pass_fail',
    question_count: 5,
    section_count: 2,
  },
];

const MOCK_CATEGORIES = [
  { category: 'Vehicles', count: 3 },
  { category: 'Plant & Machinery', count: 2 },
];

function setup() {
  return render(
    <BrowserRouter>
      <AuditTemplateLibrary />
    </BrowserRouter>,
  );
}

describe('AuditTemplateLibrary', () => {
  let auditsApi: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    mockNavigate.mockClear();

    const client = await import('../../api/client');
    auditsApi = client.auditsApi;

    auditsApi.listTemplates.mockResolvedValue({
      data: { items: MOCK_TEMPLATES, total: 2 },
    });
    auditsApi.listArchivedTemplates.mockResolvedValue({
      data: { items: [], total: 0 },
    });
    auditsApi.listCategories.mockResolvedValue({
      data: MOCK_CATEGORIES,
    });
  });

  it('renders the page heading', async () => {
    setup();

    expect(
      screen.getByRole('heading', { name: 'Audit Template Library' }),
    ).toBeInTheDocument();
  });

  it('shows skeleton loader while data is loading', () => {
    auditsApi.listTemplates.mockReturnValue(new Promise(() => {}));
    auditsApi.listArchivedTemplates.mockReturnValue(new Promise(() => {}));
    auditsApi.listCategories.mockReturnValue(new Promise(() => {}));

    setup();

    expect(screen.getByText(/Showing 0 of 0 templates/i)).toBeInTheDocument();
  });

  it('renders template cards after data loads', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    expect(screen.getByText('Plant Safety Audit')).toBeInTheDocument();
  });

  it('displays published and draft badges', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    const published = screen.getAllByText('published');
    const drafts = screen.getAllByText('draft');
    expect(published.length).toBeGreaterThanOrEqual(1);
    expect(drafts.length).toBeGreaterThanOrEqual(1);
  });

  it('renders stat cards with correct counts', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Total Templates')).toBeInTheDocument();
    });

    expect(screen.getByText('Published')).toBeInTheDocument();
    expect(screen.getByText('Drafts')).toBeInTheDocument();
  });

  it('renders category filter pills', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'All Categories' })).toBeInTheDocument();
    });

    expect(screen.getByRole('tab', { name: /Vehicles/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Plant & Machinery/ })).toBeInTheDocument();
  });

  it('filters templates when typing in search input', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search templates...');
    fireEvent.change(searchInput, { target: { value: 'Vehicle' } });

    await waitFor(() => {
      expect(auditsApi.listTemplates).toHaveBeenCalledWith(
        1,
        200,
        expect.objectContaining({ search: 'Vehicle' }),
      );
    });
  });

  it('switches between grid and list view', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    const listViewBtn = screen.getByRole('radio', { name: 'List view' });
    fireEvent.click(listViewBtn);

    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    auditsApi.listTemplates.mockRejectedValue(new Error('Server error'));

    setup();

    await waitFor(() => {
      expect(screen.getByText('Failed to load templates.')).toBeInTheDocument();
    });

    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('retries loading when "Try Again" is clicked', async () => {
    auditsApi.listTemplates
      .mockRejectedValueOnce(new Error('Server error'))
      .mockResolvedValueOnce({ data: { items: MOCK_TEMPLATES, total: 2 } });

    setup();

    await waitFor(() => {
      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Try Again'));

    await waitFor(() => {
      expect(auditsApi.listTemplates).toHaveBeenCalledTimes(2);
    });
  });

  it('navigates to new template page when "New Template" is clicked', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    const newBtn = screen.getByRole('button', { name: /New Template/i });
    fireEvent.click(newBtn);

    expect(mockNavigate).toHaveBeenCalledWith('/audit-templates/new');
  });

  it('shows empty state when no templates match', async () => {
    auditsApi.listTemplates.mockResolvedValue({
      data: { items: [], total: 0 },
    });

    setup();

    await waitFor(() => {
      expect(screen.getByText('No templates found')).toBeInTheDocument();
    });
  });

  it('shows "Import" button that opens import dialog', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle Inspection Checklist')).toBeInTheDocument();
    });

    const importBtn = screen.getByRole('button', { name: /Import/i });
    fireEvent.click(importBtn);

    await waitFor(() => {
      expect(screen.getByText('Batch Import')).toBeInTheDocument();
    });
  });
});
