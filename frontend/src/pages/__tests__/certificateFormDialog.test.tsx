/**
 * Add certificate — the register's first write surface (PX-427).
 *
 * The register had three read routes and no writer, and `addCertificate` in the
 * API client had no call site anywhere in the app, so there was no way to file a
 * dated certificate from the product at all. These tests hold the two things
 * that make the button real: it exists on both surfaces that read the register,
 * and what it sends is named for the columns it writes — not the `issued_by` /
 * `issued_date` pair the backend schema used to declare.
 */

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ComplianceAutomation from '../ComplianceAutomation'
import AssuranceCertShelfPanel from '../assurance/AssuranceCertShelfPanel'

const mockAddCertificate = vi.fn()
const mockListCertificates = vi.fn()
const mockListRegulatoryUpdates = vi.fn()
const mockGetComplianceScore = vi.fn()
const mockGetComplianceTrend = vi.fn()
const mockListRuns = vi.fn()
const mockListImpacts = vi.fn()
const mockGetAssuranceCertShelf = vi.fn()

vi.mock('../../api/client', () => ({
  complianceAutomationApi: {
    addCertificate: (...args: unknown[]) => mockAddCertificate(...args),
    listCertificates: (...args: unknown[]) => mockListCertificates(...args),
    listRegulatoryUpdates: (...args: unknown[]) => mockListRegulatoryUpdates(...args),
    getComplianceScore: (...args: unknown[]) => mockGetComplianceScore(...args),
    getComplianceTrend: (...args: unknown[]) => mockGetComplianceTrend(...args),
    getAssuranceCertShelf: (...args: unknown[]) => mockGetAssuranceCertShelf(...args),
    listRiddorSubmissions: vi.fn(),
  },
  auditsApi: { listRuns: (...args: unknown[]) => mockListRuns(...args) },
  knowledgeBankApi: {
    listImpacts: (...args: unknown[]) => mockListImpacts(...args),
    runRegulatoryWatch: vi.fn(),
    createImpactAction: vi.fn(),
    resolveImpact: vi.fn(),
  },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error ? error.message : (fallback ?? 'Something went wrong'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

beforeAll(() => {
  // Radix measures the checkbox and the select trigger, neither of which jsdom
  // can do. Same shims the other dialog form tests install.
  const proto = Element.prototype as unknown as Record<string, unknown>
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false
  if (!proto.setPointerCapture) proto.setPointerCapture = () => undefined
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => undefined
  if (!proto.scrollIntoView) proto.scrollIntoView = () => undefined
  if (!('ResizeObserver' in globalThis)) {
    ;(globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

function fillRequiredFields({ issue = '2026-08-01', expiry = '2027-08-01' } = {}) {
  fireEvent.change(screen.getByTestId('certificate-form-name-input'), {
    target: { value: 'ISO 9001:2015 Certificate' },
  })
  fireEvent.change(screen.getByTestId('certificate-form-type-input'), {
    target: { value: 'iso9001' },
  })
  fireEvent.change(screen.getByTestId('certificate-form-issue-date-input'), {
    target: { value: issue },
  })
  fireEvent.change(screen.getByTestId('certificate-form-expiry-date-input'), {
    target: { value: expiry },
  })
}

async function openDialogFromMonitoring() {
  render(
    <MemoryRouter>
      <ComplianceAutomation />
    </MemoryRouter>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Certificates' }))
  fireEvent.click(screen.getByTestId('monitoring-certificates-add'))
  return screen.findByTestId('certificate-form-dialog')
}

beforeEach(() => {
  vi.clearAllMocks()
  mockAddCertificate.mockResolvedValue({ data: { id: 1 } })
  mockListCertificates.mockResolvedValue({ data: { certificates: [], total: 0 } })
  mockListRegulatoryUpdates.mockResolvedValue({ data: { updates: [], total: 0, unreviewed: 0 } })
  mockGetComplianceScore.mockResolvedValue({ data: { overall_score: 0, categories: {} } })
  mockGetComplianceTrend.mockResolvedValue({ data: { trend: [], period_months: 12 } })
  mockListRuns.mockResolvedValue({ data: { items: [], total: 0 } })
  mockListImpacts.mockResolvedValue({ data: [] })
  mockGetAssuranceCertShelf.mockResolvedValue({
    data: {
      items: [],
      total: 0,
      summary: { valid: 0, due_soon: 0, expired: 0, unknown: 0, by_scheme: {} },
      due_soon_days: 30,
    },
  })
})

describe('Add certificate is reachable from both register surfaces', () => {
  it('opens from the Monitoring certificates tab', async () => {
    expect(await openDialogFromMonitoring()).toBeInTheDocument()
  })

  it('offers the same action from the empty register, not just the header', async () => {
    render(
      <MemoryRouter>
        <ComplianceAutomation />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Certificates' }))

    expect(screen.getByTestId('monitoring-certificates-empty')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('monitoring-certificates-empty-cta'))
    expect(await screen.findByTestId('certificate-form-dialog')).toBeInTheDocument()
  })

  it('opens from the assurance certificate shelf', async () => {
    render(
      <MemoryRouter>
        <AssuranceCertShelfPanel />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByTestId('assurance-cert-shelf-add'))
    expect(await screen.findByTestId('certificate-form-dialog')).toBeInTheDocument()
  })

  it('reloads the shelf after a certificate is filed', async () => {
    render(
      <MemoryRouter>
        <AssuranceCertShelfPanel />
      </MemoryRouter>,
    )
    await waitFor(() => expect(mockGetAssuranceCertShelf).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByTestId('assurance-cert-shelf-add'))
    await screen.findByTestId('certificate-form-dialog')
    fillRequiredFields()
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() => expect(mockGetAssuranceCertShelf).toHaveBeenCalledTimes(2))
  })
})

describe('what the form sends', () => {
  it('posts the column names the register actually stores', async () => {
    await openDialogFromMonitoring()
    fillRequiredFields()
    fireEvent.change(screen.getByTestId('certificate-form-issuing-body-input'), {
      target: { value: 'BSI' },
    })
    fireEvent.change(screen.getByTestId('certificate-form-reference-input'), {
      target: { value: 'FS 123456' },
    })
    fireEvent.change(screen.getByTestId('certificate-form-entity-name-input'), {
      target: { value: 'Plantexpand Ltd' },
    })
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() => expect(mockAddCertificate).toHaveBeenCalledTimes(1))
    const body = mockAddCertificate.mock.calls[0]![0] as Record<string, unknown>
    expect(body).toMatchObject({
      name: 'ISO 9001:2015 Certificate',
      certificate_type: 'iso9001',
      entity_type: 'organization',
      entity_name: 'Plantexpand Ltd',
      issuing_body: 'BSI',
      reference_number: 'FS 123456',
      issue_date: '2026-08-01',
      expiry_date: '2027-08-01',
      is_critical: false,
    })
    // The names the backend schema used to declare match no column, so sending
    // either would be silently discarded.
    expect(body).not.toHaveProperty('issued_by')
    expect(body).not.toHaveProperty('issued_date')
  })

  it('omits fields left blank rather than sending empty strings', async () => {
    await openDialogFromMonitoring()
    fillRequiredFields()
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() => expect(mockAddCertificate).toHaveBeenCalledTimes(1))
    const body = mockAddCertificate.mock.calls[0]![0] as Record<string, unknown>
    expect(body).not.toHaveProperty('issuing_body')
    expect(body).not.toHaveProperty('reference_number')
    expect(body).not.toHaveProperty('entity_name')
    expect(body).not.toHaveProperty('notes')
  })

  it('sends no entity_id, because the browser has no tenant id to send', async () => {
    await openDialogFromMonitoring()
    fillRequiredFields()
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() => expect(mockAddCertificate).toHaveBeenCalledTimes(1))
    expect(mockAddCertificate.mock.calls[0]![0]).not.toHaveProperty('entity_id')
  })
})

describe('the form refuses what the register cannot use', () => {
  it('will not submit without a name, type or dates', async () => {
    await openDialogFromMonitoring()
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('certificate-form-name-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('certificate-form-expiry-date-error')).toBeInTheDocument()
    expect(mockAddCertificate).not.toHaveBeenCalled()
  })

  it('rejects an expiry before the issue date without a round trip', async () => {
    await openDialogFromMonitoring()
    fillRequiredFields({ issue: '2027-08-01', expiry: '2026-08-01' })
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('certificate-form-expiry-date-error')).toHaveTextContent(
        'Expiry date cannot be earlier than the issue date',
      ),
    )
    expect(mockAddCertificate).not.toHaveBeenCalled()
  })

  it('keeps the dialog open and shows why when the write fails', async () => {
    mockAddCertificate.mockRejectedValue(new Error('Certificate type must be 50 characters or fewer'))
    await openDialogFromMonitoring()
    fillRequiredFields()
    fireEvent.click(screen.getByTestId('certificate-form-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('certificate-form-error')).toHaveTextContent(
        'Certificate type must be 50 characters or fewer',
      ),
    )
    expect(screen.getByTestId('certificate-form-dialog')).toBeInTheDocument()
  })
})
