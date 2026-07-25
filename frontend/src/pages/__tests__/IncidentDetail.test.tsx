import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import IncidentDetail from '../IncidentDetail'

const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | Record<string, unknown>) =>
      typeof fallbackOrOptions === 'string' ? fallbackOrOptions : key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '11' }),
  }
})

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('../../components/ui/Breadcrumbs', () => ({
  Breadcrumbs: () => <div data-testid="breadcrumbs" />,
}))

vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: () => <input data-testid="engineer-people-picker" />,
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({ children, defaultValue }: { children: ReactNode; defaultValue?: string }) => (
    <div data-testid="incident-tabs" data-default-tab={defaultValue}>{children}</div>
  ),
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({
    children,
    ...rest
  }: {
    children: ReactNode
    value?: string
    'data-testid'?: string
  }) => (
    <button type="button" data-testid={rest['data-testid']}>
      {children}
    </button>
  ),
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('../../components/StandardsAssessmentPanel', () => ({
  StandardsAssessmentPanel: ({
    entityType,
    entityId,
  }: {
    entityType: string
    entityId: number | string
  }) => (
    <div data-testid="standards-assessment-panel-mock">
      {entityType}:{entityId}
    </div>
  ),
}))

vi.mock('../../api/client', () => ({
  incidentsApi: {
    get: vi.fn(),
    update: vi.fn(),
    raiseRisk: vi.fn(),
    listInvestigations: vi.fn(),
    listRunningSheet: vi.fn(),
    addRunningSheetEntry: vi.fn(),
    deleteRunningSheetEntry: vi.fn(),
  },
  investigationsApi: {
    createFromRecord: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  evidenceAssetsApi: {
    list: vi.fn(),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  lookupsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  contractsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  complianceAutomationApi: {
    checkRiddor: vi.fn(),
    prepareRiddor: vi.fn(),
  },
  getApiErrorMessage: (err: Error, fallback?: string) => err.message || fallback || 'error',
}))

const incidentRecord = {
  id: 11,
  reference_number: 'INC-11',
  title: 'Loader slip',
  description: 'A colleague slipped on a wet access point.',
  incident_type: 'injury',
  severity: 'high',
  status: 'reported',
  incident_date: '2026-03-12T09:45:00Z',
  location: 'North gate',
  department: 'Facilities',
  reported_date: '2026-03-12T10:00:00Z',
  created_at: '2026-03-12T10:05:00Z',
  updated_at: '2026-03-12T10:05:00Z',
  reporter_name: 'Alice Reporter',
  reporter_email: 'alice@example.com',
  people_involved: 'Bob Worker',
  first_aid_given: true,
  emergency_services_called: true,
  reporter_submission: {
    contract: 'facilities',
    person_name: 'Bob Worker',
    person_role: 'Cleaner',
    witness_names: 'Jane Witness',
    medical_assistance: 'ambulance',
    has_injuries: true,
    photos: { count: 2 },
  },
}

function renderPage() {
  return render(
    <BrowserRouter>
      <IncidentDetail />
    </BrowserRouter>,
  )
}

describe('IncidentDetail', () => {
  let client: Awaited<typeof import('../../api/client')>

  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
    client = await import('../../api/client')
    client.incidentsApi.get.mockResolvedValue({ data: incidentRecord })
    client.incidentsApi.listInvestigations.mockResolvedValue({
      data: { items: [{ id: 21, reference_number: 'INV-21', title: 'Linked investigation' }], total: 1 },
    })
    client.incidentsApi.listRunningSheet.mockResolvedValue({ data: [] })
    client.actionsApi.list.mockResolvedValue({
      data: { items: [{ id: 1, title: 'Secure CCTV', status: 'open' }] },
    })
    client.evidenceAssetsApi.list.mockResolvedValue({ data: { items: [] } })
  })

  it('surfaces reporter, impact, and submission details on first view', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    expect(screen.getAllByText('Alice Reporter').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Bob Worker').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2 uploaded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INV-21').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Jane Witness').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ambulance').length).toBeGreaterThan(0)
  })

  it('opens the linked investigation and filtered CAPA workspace', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByRole('button', { name: 'incidents.detail.open_investigation' })[0])
    expect(mockNavigate).toHaveBeenCalledWith('/investigations/21')

    fireEvent.click(screen.getByTestId('incident-open-capa'))
    expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=incident&sourceId=11')
  })

  it('offers Add Action (RTA parity) when no actions are linked', async () => {
    client.actionsApi.list.mockResolvedValue({ data: { items: [] } })

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    expect(screen.queryByTestId('incident-capa-handoff-cta')).not.toBeInTheDocument()
    expect(
      screen.getByText('No CAPA actions linked yet — use Add Action to create one.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('incident-add-action')).toBeInTheDocument()
    expect(screen.getByTestId('incident-actions-tab')).toBeInTheDocument()
  })

  it('surfaces incident evidence assets instead of relying only on reporter metadata', async () => {
    client.evidenceAssetsApi.list.mockResolvedValue({
      data: {
        items: [
          {
            id: 51,
            title: 'Scene photograph',
            original_filename: 'scene.jpg',
            content_type: 'image/jpeg',
          },
        ],
      },
    })

    renderPage()

    expect(await screen.findByTestId('incident-evidence-assets')).toHaveTextContent('Scene photograph')
    expect(screen.getAllByText('1 evidence asset').length).toBeGreaterThan(0)
    expect(client.evidenceAssetsApi.list).toHaveBeenCalledWith({
      source_module: 'incident',
      source_id: 11,
      page_size: 50,
    })
  })

  it('renders workflow proof counts without faux zeros when CAPA load fails', async () => {
    const { toast } = await import('../../contexts/ToastContext')
    client.actionsApi.list.mockRejectedValue(new Error('actions down'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('incident-workflow-proof')).toBeInTheDocument()
    })

    expect(screen.getByTestId('incident-capa-count')).toHaveTextContent('—')
    expect(toast.error).toHaveBeenCalled()
    expect(screen.queryByTestId('incident-capa-handoff-cta')).not.toBeInTheDocument()
    expect(
      screen.queryByText('No CAPA actions linked yet — use Add Action to create one.'),
    ).not.toBeInTheDocument()
    expect(
      screen.getAllByText('CAPA actions could not be loaded — counts may be incomplete.').length,
    ).toBeGreaterThan(0)
    expect(screen.getByTestId('incident-actions-tab')).toHaveTextContent('—')
  })

  it('hosts StandardsAssessmentPanel like Near Miss (incident entity)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('incident-standards-panel')).toBeInTheDocument()
    })
    expect(screen.getByTestId('standards-assessment-panel-mock')).toHaveTextContent('incident:11')
  })

  it('surfaces toast when incident edit save fails (PX-002)', async () => {
    const { toast } = await import('../../contexts/ToastContext')
    client.incidentsApi.update.mockRejectedValue(new Error('Conflict: cannot transition'))

    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'edit' }))
    fireEvent.click(screen.getByRole('button', { name: 'incidents.detail.save_changes' }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Conflict: cannot transition')
    })
  })

  it('omits unchanged status on save so reported→reported never patches status', async () => {
    client.incidentsApi.update.mockResolvedValue({ data: incidentRecord })

    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'edit' }))
    fireEvent.click(screen.getByRole('button', { name: 'incidents.detail.save_changes' }))

    await waitFor(() => {
      expect(client.incidentsApi.update).toHaveBeenCalled()
    })
    const payload = client.incidentsApi.update.mock.calls[0][1]
    expect(payload.status).toBeUndefined()
  })

  it('adds and saves structured witnesses on the shared Witnesses tab', async () => {
    client.incidentsApi.update.mockResolvedValue({
      data: { ...incidentRecord, witnesses_structured: { witnesses: [{ name: 'Jane Witness' }] } },
    })

    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('incident-witnesses-add'))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Jane Witness' } })
    fireEvent.click(screen.getByTestId('incident-witnesses-save'))

    await waitFor(() => {
      expect(client.incidentsApi.update).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          witnesses_structured: { witnesses: [expect.objectContaining({ name: 'Jane Witness' })] },
        }),
      )
    })
  })

  it('renders the shared Photos tab wired to evidence-assets upload', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('incident-evidence-panel')).toBeInTheDocument()
    })
    expect(client.evidenceAssetsApi.list).toHaveBeenCalledWith({
      source_module: 'incident',
      source_id: 11,
      page_size: 50,
    })
  })
})
