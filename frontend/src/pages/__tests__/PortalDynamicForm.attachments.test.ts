/**
 * PX-327: attached evidence was silently discarded on submit.
 *
 * The portal listed the user's photos, then serialised them with
 * `JSON.stringify`, which turns a `File` into `{}`. One JSON POST went out
 * carrying no file data, the record was stored with no attachments, and the
 * user was shown a reference number and told it had succeeded.
 *
 * These tests watch the wire, because that is where the evidence vanished.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  formTemplatesApi: { getBySlug: vi.fn() },
  lookupsApi: { list: vi.fn() },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'Request failed'),
}))

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({ user: null }),
}))

import {
  buildPortalReportPayload,
  buildReporterSubmission,
  collectFormFiles,
  extractApiMessage,
  submitPortalReportWithAttachments,
} from '../PortalDynamicForm'

function photo(name = 'scene.jpg', bytes = 'binary-content') {
  return new File([bytes], name, { type: 'image/jpeg' })
}

function nearMissForm(overrides: Record<string, unknown> = {}) {
  return {
    contract: 'ACME',
    location: 'Loading Bay 3',
    description: 'Forklift nearly struck a pedestrian near the loading bay.',
    ...overrides,
  }
}

interface RecordedRequest {
  url: string
  method: string
  body: unknown
}

let requests: RecordedRequest[]
let uploadCounter: number

function jsonResponse(body: unknown, ok = true, statusCode = 200) {
  return {
    ok,
    status: statusCode,
    json: async () => body,
  } as Response
}

beforeEach(() => {
  requests = []
  uploadCounter = 0

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      requests.push({ url, method: init.method ?? 'GET', body: init.body })

      if (url.includes('/reports/attachments')) {
        uploadCounter += 1
        return jsonResponse(
          {
            attachment_id: `${uploadCounter}.token-${uploadCounter}`,
            filename: `file-${uploadCounter}`,
            content_type: 'image/jpeg',
            size_bytes: 128,
          },
          true,
          201,
        )
      }

      return jsonResponse(
        {
          success: true,
          reference_number: 'NM-2026-6D3DE96F',
          tracking_code: 'TRACK123',
          message: 'ok',
          estimated_response: '24 hours',
        },
        true,
        201,
      )
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('collectFormFiles', () => {
  it('finds files held in an array field and remembers which field they came from', () => {
    const first = photo('one.jpg')
    const second = photo('two.jpg')

    const collected = collectFormFiles(nearMissForm({ photos: [first, second] }))

    expect(collected).toEqual([
      { field: 'photos', file: first },
      { field: 'photos', file: second },
    ])
  })

  it('finds a file held directly on a field', () => {
    const single = photo('solo.jpg')

    expect(collectFormFiles({ evidence: single })).toEqual([{ field: 'evidence', file: single }])
  })

  it('returns nothing when the form holds no files', () => {
    expect(collectFormFiles(nearMissForm())).toEqual([])
  })
})

describe('submitPortalReportWithAttachments', () => {
  it('uploads every attached file and links them to the submitted report', async () => {
    await submitPortalReportWithAttachments({
      formType: 'near-miss',
      formData: nearMissForm({ photos: [photo('one.jpg'), photo('two.jpg')] }),
      templateName: 'Near Miss Report',
      user: null,
    })

    const uploads = requests.filter((request) => request.url.includes('/reports/attachments'))
    const submits = requests.filter((request) => request.url.endsWith('/portal/reports/'))

    // The original defect: exactly one non-GET request went out, and it was JSON.
    expect(uploads).toHaveLength(2)
    expect(submits).toHaveLength(1)

    for (const upload of uploads) {
      expect(upload.method).toBe('POST')
      expect(upload.body).toBeInstanceOf(FormData)
    }

    const uploadedNames = uploads.map((upload) => ((upload.body as FormData).get('file') as File).name)
    expect(uploadedNames).toEqual(['one.jpg', 'two.jpg'])

    const submitted = JSON.parse(submits[0].body as string)
    expect(submitted.attachment_ids).toEqual(['1.token-1', '2.token-2'])
  })

  it('tells the API which kind of report each upload belongs to', async () => {
    await submitPortalReportWithAttachments({
      formType: 'near-miss',
      formData: nearMissForm({ photos: [photo()] }),
      user: null,
    })

    const upload = requests.find((request) => request.url.includes('/reports/attachments'))
    expect((upload?.body as FormData).get('report_type')).toBe('near_miss')
  })

  it('never puts raw File objects on the wire', async () => {
    await submitPortalReportWithAttachments({
      formType: 'near-miss',
      formData: nearMissForm({ photos: [photo('one.jpg')] }),
      user: null,
    })

    const submitted = requests.find((request) => request.url.endsWith('/portal/reports/'))
    const body = submitted?.body as string

    // A File serialises to `{}`. Before the fix the payload carried `"photos":[{}]`,
    // which is exactly what "listed in the UI, absent from the record" looks like.
    expect(body).not.toContain('[{}]')
    expect(body).toContain('one.jpg')

    const parsed = JSON.parse(body)
    expect(parsed.reporter_submission.photos.files).toEqual([
      { attachment_id: '1.token-1', name: 'one.jpg', type: 'image/jpeg', size: expect.any(Number) },
    ])
  })

  it('submits a single JSON request and no attachment_ids when nothing was attached', async () => {
    await submitPortalReportWithAttachments({
      formType: 'near-miss',
      formData: nearMissForm(),
      user: null,
    })

    expect(requests).toHaveLength(1)
    const submitted = JSON.parse(requests[0].body as string)
    expect(submitted).not.toHaveProperty('attachment_ids')
  })
})

describe('submitPortalReportWithAttachments when an upload fails', () => {
  it('does not submit the report, so the user is never told a lossy submission succeeded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init: RequestInit = {}) => {
        requests.push({ url, method: init.method ?? 'GET', body: init.body })
        if (url.includes('/reports/attachments')) {
          // The API's real error envelope, as returned by src/api/utils/errors.py.
          return jsonResponse(
            {
              error: {
                code: 'ErrorCode.VALIDATION_ERROR',
                message: "Files of type 'video/mp4' cannot be attached to a portal report.",
              },
            },
            false,
            422,
          )
        }
        return jsonResponse({ reference_number: 'NM-SHOULD-NOT-HAPPEN' }, true, 201)
      }),
    )

    await expect(
      submitPortalReportWithAttachments({
        formType: 'near-miss',
        formData: nearMissForm({ photos: [photo('clip.mp4')] }),
        user: null,
      }),
    ).rejects.toThrow(/clip\.mp4.*cannot be attached to a portal report/s)

    expect(requests.filter((request) => request.url.endsWith('/portal/reports/'))).toHaveLength(0)
  })

  it('names the file and says the report was not submitted', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Network request failed')
      }),
    )

    await expect(
      submitPortalReportWithAttachments({
        formType: 'near-miss',
        formData: nearMissForm({ photos: [photo('one.jpg')] }),
        user: null,
      }),
    ).rejects.toThrow(/"one\.jpg".*has not been submitted/s)
  })

  it('stops at the first failure rather than uploading the rest', async () => {
    let attempts = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/reports/attachments')) {
          attempts += 1
          return jsonResponse({ message: 'Upload rejected.' }, false, 422)
        }
        return jsonResponse({ reference_number: 'NM-NOPE' }, true, 201)
      }),
    )

    await expect(
      submitPortalReportWithAttachments({
        formType: 'near-miss',
        formData: nearMissForm({ photos: [photo('one.jpg'), photo('two.jpg'), photo('three.jpg')] }),
        user: null,
      }),
    ).rejects.toThrow()

    expect(attempts).toBe(1)
  })
})

describe('extractApiMessage', () => {
  it('reads the API error envelope, so the user sees the actual reason', () => {
    const body = {
      error: {
        code: 'ErrorCode.VALIDATION_ERROR',
        message: "Files of type 'application/x-msdownload' cannot be attached to a portal report.",
        details: { allowed_types: ['image/jpeg'] },
      },
    }

    expect(extractApiMessage(body, 'fallback')).toBe(
      "Files of type 'application/x-msdownload' cannot be attached to a portal report.",
    )
  })

  it('reads a FastAPI validation detail', () => {
    expect(extractApiMessage({ detail: 'Field required' }, 'fallback')).toBe('Field required')
    expect(extractApiMessage({ detail: { message: 'Nested reason' } }, 'fallback')).toBe('Nested reason')
  })

  it('falls back only when the body carries no usable message', () => {
    expect(extractApiMessage({}, 'fallback')).toBe('fallback')
    expect(extractApiMessage(null, 'fallback')).toBe('fallback')
    expect(extractApiMessage('not json', 'fallback')).toBe('fallback')
  })
})

describe('buildReporterSubmission', () => {
  it('records what was stored instead of the unserialisable File', () => {
    const submission = buildReporterSubmission(nearMissForm({ photos: [photo('one.jpg')] }), [
      {
        field: 'photos',
        attachment_id: '7.tok',
        name: 'one.jpg',
        type: 'image/jpeg',
        size: 2048,
      },
    ])

    expect(submission.photos).toEqual({
      count: 1,
      files: [{ attachment_id: '7.tok', name: 'one.jpg', type: 'image/jpeg', size: 2048 }],
      evidence_spine: 'evidence_assets',
    })
    expect(submission.description).toBe(nearMissForm().description)
  })

  it('leaves non-file fields untouched', () => {
    const submission = buildReporterSubmission(nearMissForm({ was_involved: true, witnesses: ['Jo'] }))

    expect(submission.was_involved).toBe(true)
    expect(submission.witnesses).toEqual(['Jo'])
  })
})

describe('buildPortalReportPayload', () => {
  it('omits attachment_ids entirely when there is nothing to link', () => {
    const payload = buildPortalReportPayload({
      formType: 'near-miss',
      formData: nearMissForm(),
      user: null,
    })

    expect(payload).not.toHaveProperty('attachment_ids')
  })

  it('does not serialise attached files into empty objects', () => {
    const payload = buildPortalReportPayload({
      formType: 'near-miss',
      formData: nearMissForm({ photos: [photo('one.jpg')] }),
      user: null,
    })

    // The defect in one line: spreading formData put `File` objects into
    // reporter_submission, and JSON.stringify rendered them as `[{}]`.
    expect(JSON.stringify(payload)).not.toContain('"photos":[{}]')
  })

  it('carries every attachment handle through to the payload', () => {
    const payload = buildPortalReportPayload({
      formType: 'near-miss',
      formData: nearMissForm({ photos: [photo('one.jpg')] }),
      user: null,
      attachments: [
        { field: 'photos', attachment_id: '3.abc', name: 'one.jpg', type: 'image/jpeg', size: 10 },
      ],
    })

    expect(payload.attachment_ids).toEqual(['3.abc'])
  })
})
