import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CaseEvidencePanel } from '../CaseEvidencePanel'
import { evidenceAssetsApi, type EvidenceAsset } from '../../../api/client'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string }) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) return opts.defaultValue
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../../../api/client', async () => {
  const actual =
    await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    evidenceAssetsApi: {
      list: vi.fn(),
      upload: vi.fn(),
      delete: vi.fn(),
      getSignedUrl: vi.fn(),
    },
  }
})

const asset = (id: number, filename: string): EvidenceAsset => ({
  id,
  storage_key: `evidence/incident/1/${filename}`,
  original_filename: filename,
  content_type: 'image/jpeg',
  asset_type: 'photo',
  source_module: 'incident',
  source_id: 1,
  visibility: 'internal_customer',
  contains_pii: false,
  redaction_required: false,
  retention_policy: 'standard',
  created_at: '2026-07-22T10:00:00Z',
  updated_at: '2026-07-22T10:00:00Z',
})

const listResponse = (items: EvidenceAsset[]) =>
  ({ data: { items, total: items.length, page: 1, page_size: 50, total_pages: 1 } }) as never

describe('CaseEvidencePanel', () => {
  beforeEach(() => {
    vi.mocked(evidenceAssetsApi.list).mockReset()
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockReset()
    vi.mocked(evidenceAssetsApi.delete).mockReset()
  })

  it('loads and lists evidence for the given source', async () => {
    vi.mocked(evidenceAssetsApi.list).mockResolvedValue(listResponse([asset(1, 'scene.jpg')]))
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/scene.jpg' },
    } as never)

    render(<CaseEvidencePanel sourceType="incident" sourceId={1} testIdPrefix="incident" />)

    expect(await screen.findByAltText('scene.jpg')).toBeInTheDocument()
    expect(evidenceAssetsApi.list).toHaveBeenCalledWith({
      source_module: 'incident',
      source_id: 1,
      page_size: 50,
    })
    expect(screen.getByTestId('incident-evidence-panel')).toBeInTheDocument()
  })

  it('shows an empty state with no upload control when uploads are disabled', async () => {
    vi.mocked(evidenceAssetsApi.list).mockResolvedValue(listResponse([]))

    render(<CaseEvidencePanel sourceType="road_traffic_collision" sourceId={9} />)

    expect(await screen.findByText('No evidence uploaded yet')).toBeInTheDocument()
    expect(
      screen.getByText('Upload photos, videos, or documents to attach evidence to this case.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Upload evidence')).not.toBeInTheDocument()
  })

  it('renders the upload control when enableUpload is set', async () => {
    vi.mocked(evidenceAssetsApi.list).mockResolvedValue(listResponse([]))

    render(<CaseEvidencePanel sourceType="complaint" sourceId={4} enableUpload />)

    await screen.findByText('No evidence uploaded yet')
    expect(screen.getByText('Upload evidence')).toBeInTheDocument()
  })

  it('deletes evidence and refreshes the list', async () => {
    vi.mocked(evidenceAssetsApi.list)
      .mockResolvedValueOnce(listResponse([asset(1, 'scene.jpg')]))
      .mockResolvedValueOnce(listResponse([]))
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/scene.jpg' },
    } as never)
    vi.mocked(evidenceAssetsApi.delete).mockResolvedValue({} as never)

    render(<CaseEvidencePanel sourceType="near_miss" sourceId={2} />)

    await screen.findByAltText('scene.jpg')
    fireEvent.click(screen.getByLabelText('Delete scene.jpg'))

    await waitFor(() => expect(evidenceAssetsApi.delete).toHaveBeenCalledWith(1))
    await waitFor(() => expect(evidenceAssetsApi.list).toHaveBeenCalledTimes(2))
  })
})
