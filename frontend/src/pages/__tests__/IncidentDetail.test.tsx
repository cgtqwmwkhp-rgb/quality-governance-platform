import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import IncidentDetail from '../IncidentDetail'

const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | Record<string, unknown>) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (key === 'incidents.detail.reported_on' && fallbackOrOptions && 'date' in fallbackOrOptions) {
        return `Reported on ${String(fallbackOrOptions.date)}`
      }
      return key
    },
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
  Breadcrumbs: ({
    items,
  }: {
    items: Array<{ label: string; href?: string }>
  }) => (
    <nav data-testid="breadcrumbs">
      {items.map((item) => (
        <span key={item.label}>{item.label}</span>
      ))}
    </nav>
  ),
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
  ErrorClass: { NOT_FOUND: 'NOT_FOUND', SERVER_ERROR: 'SERVER_ERROR' },
  classifyError: (err: unknown) =>
    (err as { status?: number })?.status === 404 ? 'NOT_FOUND' : 'SERVER_ERROR',
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
    expect(screen.getByText('Injury reported')).toBeInTheDocument()
  })

  it.each([
    { has_injuries: 'no' as const, expected: 'No injury flagged' },
    { has_injuries: 'yes' as const, expected: 'Injury reported' },
    { has_injuries: true as const, expected: 'Injury reported' },
  ])(
    'Quick Info Impact treats has_injuries=$has_injuries as "$expected"',
    async ({ has_injuries, expected }) => {
      client.incidentsApi.get.mockResolvedValue({
        data: {
          ...incidentRecord,
          is_injury: false,
          reporter_submission: {
            ...(incidentRecord.reporter_submission as object),
            has_injuries,
          },
        },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
      })

      expect(screen.getByText(expected)).toBeInTheDocument()
      if (expected === 'No injury flagged') {
        expect(screen.queryByText('Injury reported')).not.toBeInTheDocument()
      } else {
        expect(screen.queryByText('No injury flagged')).not.toBeInTheDocument()
      }
    },
  )

  it('opens the linked investigation and filtered CAPA workspace', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'incidents.detail.open_investigation' }))
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

  it('PX-164: severity and status badges use title case, not raw lowercase codes', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    expect(screen.getAllByText('High').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Reported').length).toBeGreaterThan(0)
    expect(screen.queryByText('high')).not.toBeInTheDocument()
    expect(screen.queryByText('reported')).not.toBeInTheDocument()
  })

  it('PX-176: reported-on header includes the formatted date, not a bare label', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Reported on 12/03/2026')).toBeInTheDocument()
    })
  })

  it('PX-175: only one Start/Open investigation control is rendered on the page', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    expect(
      screen.getAllByRole('button', { name: 'incidents.detail.open_investigation' }),
    ).toHaveLength(1)
  })

  it('PX-208: a failed edit save leaves a persistent error on the page, not just a toast', async () => {
    client.incidentsApi.update.mockRejectedValue(new Error('Conflict: cannot transition'))

    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'edit' }))
    fireEvent.click(screen.getByRole('button', { name: 'incidents.detail.save_changes' }))

    const notice = await screen.findByTestId('incident-save-error')
    expect(notice).toHaveTextContent('Conflict: cannot transition')
    expect(notice).toHaveTextContent('Changes were not saved')
    expect(notice).toHaveAttribute('role', 'alert')

    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(screen.getByTestId('incident-save-error')).toBeInTheDocument()
  })

  it('PX-208: witness save failures also leave a persistent error banner', async () => {
    client.incidentsApi.update.mockRejectedValue(new Error('Witness save rejected'))

    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('incident-witnesses-add'))
    fireEvent.click(screen.getByTestId('incident-witnesses-save'))

    const notice = await screen.findByTestId('incident-witness-save-error')
    expect(notice).toHaveTextContent('Witness save rejected')
  })

  it('linked investigation in workflow proof navigates to the investigation workspace', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('incident-linked-investigation')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('incident-linked-investigation'))
    expect(mockNavigate).toHaveBeenCalledWith('/investigations/21')
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

  it('renders the shared Evidence tab wired to evidence-assets upload', async () => {
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

  it('reports a failed detail fetch as a failure with retry, not as "not found" (PX-170)', async () => {
    client.incidentsApi.get.mockRejectedValue(new Error('503 Service Unavailable'))

    renderPage()

    const failure = await screen.findByTestId('incident-detail-async-error')
    expect(failure).toHaveTextContent('incidents.detail.failed_to_load')
    expect(failure).toHaveTextContent('503 Service Unavailable')
    // A degraded API must not be reported as the case not existing.
    expect(screen.queryByText('incidents.detail.not_found')).not.toBeInTheDocument()
    // The skeleton must not be left on screen either.
    expect(screen.queryByTestId('incident-detail-async')).not.toBeInTheDocument()

    client.incidentsApi.get.mockResolvedValue({ data: incidentRecord })
    fireEvent.click(screen.getByTestId('incident-detail-async-error-retry'))

    await waitFor(() => {
      expect(screen.getByText('Loader slip')).toBeInTheDocument()
    })
  })

  it('still reports a genuine 404 as not found rather than a retryable failure', async () => {
    const notFound = Object.assign(new Error('Not Found'), { status: 404 })
    client.incidentsApi.get.mockRejectedValue(notFound)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('incidents.detail.not_found')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('incident-detail-async-error')).not.toBeInTheDocument()
  })

  it('PX-174: breadcrumb and linked asset hide surrogate #ids', async () => {
    client.incidentsApi.get.mockResolvedValue({
      data: {
        ...incidentRecord,
        asset_id: 40,
        linked_risk_ids: '204',
        contract_id: 12,
        department: null,
        reporter_submission: { ...(incidentRecord.reporter_submission as object), contract: null },
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Loader slip' })).toBeInTheDocument()
    })

    const crumbs = screen.getByTestId('breadcrumbs')
    expect(crumbs).toHaveTextContent('INC-11')
    expect(crumbs).not.toHaveTextContent('#11')
    expect(screen.getAllByText('Linked asset').length).toBeGreaterThan(0)
    expect(screen.queryByText('Asset #40')).not.toBeInTheDocument()
    expect(screen.getByText('Linked risk')).toBeInTheDocument()
    expect(screen.queryByText('Risk #204')).not.toBeInTheDocument()
    expect(screen.getAllByText('Contract on record').length).toBeGreaterThan(0)
    expect(screen.queryByText('Contract #12')).not.toBeInTheDocument()
  })
})
