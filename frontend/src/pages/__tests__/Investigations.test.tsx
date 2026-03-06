import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Investigations from '../Investigations';

const mockNavigate = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'investigations.title': 'Investigations',
        'investigations.subtitle': 'Root cause analysis and corrective actions',
        'investigations.new': 'New Investigation',
        'investigations.search_placeholder': 'Search investigations...',
        'investigations.five_whys': '5 Whys Analysis',
        'investigations.root_cause': 'Root Cause',
        'investigations.corrective_actions': 'Corrective Actions',
        'investigations.add_action': 'Add Action',
        'investigations.add_action_desc': 'Create a corrective action for this investigation',
        'investigations.empty.title': 'No investigations yet',
        'investigations.stats.total': 'Total',
        'investigations.stats.completed': 'Completed',
        'status.in_progress': 'In Progress',
        'status.under_review': 'Under Review',
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
  investigationsApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    createFromRecord: vi.fn(),
    listSourceRecords: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
  },
  getApiErrorMessage: (err: any) => err?.message || 'Unknown error',
}));

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}));

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: ({ value, onChange, label }: any) => (
    <div>
      <label>{label}</label>
      <input
        data-testid="user-email-search"
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
      />
    </div>
  ),
}));

const MOCK_INVESTIGATIONS = [
  {
    id: 1,
    reference_number: 'INV-001',
    template_id: 1,
    assigned_entity_type: 'road_traffic_collision' as const,
    assigned_entity_id: 10,
    status: 'in_progress' as const,
    title: 'Vehicle collision on A1 motorway',
    description: 'Investigating root cause of collision',
    data: {},
    created_at: '2026-02-01T00:00:00Z',
  },
  {
    id: 2,
    reference_number: 'INV-002',
    template_id: 1,
    assigned_entity_type: 'reporting_incident' as const,
    assigned_entity_id: 20,
    status: 'completed' as const,
    title: 'Warehouse safety incident',
    description: 'Completed investigation into safety breach',
    data: { why_1: 'Poor lighting', why_2: 'Budget cuts', why_3: 'No maintenance' },
    created_at: '2026-01-15T00:00:00Z',
    completed_at: '2026-02-20T00:00:00Z',
  },
  {
    id: 3,
    reference_number: 'INV-003',
    template_id: 2,
    assigned_entity_type: 'complaint' as const,
    assigned_entity_id: 30,
    status: 'draft' as const,
    title: 'Customer complaint follow-up',
    data: {},
    created_at: '2026-03-01T00:00:00Z',
  },
];

function setup() {
  return render(
    <BrowserRouter>
      <Investigations />
    </BrowserRouter>,
  );
}

describe('Investigations', () => {
  let investigationsApi: any;
  let actionsApi: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    mockNavigate.mockClear();

    const client = await import('../../api/client');
    investigationsApi = client.investigationsApi;
    actionsApi = client.actionsApi;

    investigationsApi.list.mockResolvedValue({
      data: { items: MOCK_INVESTIGATIONS, total: 3 },
    });
    actionsApi.list.mockResolvedValue({
      data: { items: [] },
    });
  });

  it('shows loading spinner initially', () => {
    investigationsApi.list.mockReturnValue(new Promise(() => {}));

    setup();

    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('renders page heading after data loads', async () => {
    setup();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Investigations' }),
      ).toBeInTheDocument();
    });
  });

  it('renders investigation cards after data loads', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument();
    });

    expect(screen.getByText('Warehouse safety incident')).toBeInTheDocument();
    expect(screen.getByText('Customer complaint follow-up')).toBeInTheDocument();
  });

  it('displays reference numbers on cards', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('INV-001')).toBeInTheDocument();
    });

    expect(screen.getByText('INV-002')).toBeInTheDocument();
    expect(screen.getByText('INV-003')).toBeInTheDocument();
  });

  it('renders stat cards with correct counts', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Total')).toBeInTheDocument();
    });

    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Under Review')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('filters investigations by search term', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search investigations...');
    fireEvent.change(searchInput, { target: { value: 'warehouse' } });

    expect(screen.queryByText('Vehicle collision on A1 motorway')).not.toBeInTheDocument();
    expect(screen.getByText('Warehouse safety incident')).toBeInTheDocument();
  });

  it('filters by reference number', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('INV-001')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search investigations...');
    fireEvent.change(searchInput, { target: { value: 'INV-003' } });

    expect(screen.queryByText('Vehicle collision on A1 motorway')).not.toBeInTheDocument();
    expect(screen.getByText('Customer complaint follow-up')).toBeInTheDocument();
  });

  it('opens detail modal when clicking an investigation card', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Vehicle collision on A1 motorway'));

    await waitFor(() => {
      expect(screen.getByText('5 Whys Analysis')).toBeInTheDocument();
    });
  });

  it('shows empty state when no investigations exist', async () => {
    investigationsApi.list.mockResolvedValue({
      data: { items: [], total: 0 },
    });

    setup();

    await waitFor(() => {
      expect(screen.getByText('No investigations yet')).toBeInTheDocument();
    });
  });

  it('shows empty state when search has no results', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search investigations...');
    fireEvent.change(searchInput, { target: { value: 'nonexistent query xyz' } });

    expect(screen.getByText('No investigations yet')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    investigationsApi.list.mockRejectedValue(new Error('Network failure'));

    setup();

    await waitFor(() => {
      expect(screen.getByText('No investigations yet')).toBeInTheDocument();
    });

    const { trackError } = await import('../../utils/errorTracker');
    expect(trackError).toHaveBeenCalled();
  });

  it('shows "New Investigation" button', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument();
    });

    expect(
      screen.getByRole('button', { name: /New Investigation/i }),
    ).toBeInTheDocument();
  });

  it('shows RCA preview for investigations with data', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('Warehouse safety incident')).toBeInTheDocument();
    });

    expect(screen.getByText('Root Cause Analysis')).toBeInTheDocument();
    expect(screen.getByText('Poor lighting')).toBeInTheDocument();
  });

  it('shows entity type labels on cards', async () => {
    setup();

    await waitFor(() => {
      expect(screen.getByText('road traffic collision')).toBeInTheDocument();
    });

    expect(screen.getByText('reporting incident')).toBeInTheDocument();
    expect(screen.getByText('complaint')).toBeInTheDocument();
  });
});
