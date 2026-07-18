import { describe, expect, it } from 'vitest'
import {
  MAP_W3_LINK_STATUSES,
  MAP_W3_TRAIL_ACTIONS,
  appendAssistRerunTrail,
  buildSourceFingerprint,
  computeRescoreHonesty,
  detectStaleReason,
  fingerprintQuestionText,
  markStaleLinks,
  shouldPromptResuggest,
  type MapW3StandardLink,
} from '../mapW3StaleRescoreHonesty'

const question = {
  questionId: 'q-1',
  questionText: 'Is the emergency exit clear?',
  description: 'Check daily',
}

function acceptedLink(overrides: Partial<MapW3StandardLink> = {}): MapW3StandardLink {
  const fp = buildSourceFingerprint(question, 'lib-v1')
  return {
    id: 'link-1',
    questionId: 'q-1',
    scheme: 'ISO',
    refId: '45001-8.2',
    label: 'ISO 45001 8.2',
    confidence: 0.91,
    status: 'accepted',
    sourceFingerprint: fp,
    libraryVersion: 'lib-v1',
    ...overrides,
  }
}

describe('mapW3StaleRescoreHonesty MAP-W3', () => {
  it('exposes link statuses including stale and Assist trail actions', () => {
    expect(MAP_W3_LINK_STATUSES).toContain('stale')
    expect(MAP_W3_TRAIL_ACTIONS).toEqual(
      expect.arrayContaining(['marked_stale', 'assist_rerun']),
    )
  })

  it('fingerprints question text stably and ignores whitespace/case noise', () => {
    const a = fingerprintQuestionText('Exit clear?', 'Check daily')
    const b = fingerprintQuestionText('  exit   clear? ', 'CHECK DAILY')
    expect(a).toBe(b)
    expect(a.startsWith('qfp_')).toBe(true)
  })

  it('detects stale reason when question text changes', () => {
    const link = acceptedLink()
    const reason = detectStaleReason(
      link,
      { ...question, questionText: 'Is the fire exit blocked?' },
      'lib-v1',
    )
    expect(reason).toBe('question_text_changed')
  })

  it('detects stale reason when library version changes', () => {
    const link = acceptedLink()
    expect(detectStaleReason(link, question, 'lib-v2')).toBe('library_version_changed')
  })

  it('detects both when text and library drift together', () => {
    const link = acceptedLink()
    expect(
      detectStaleReason(
        link,
        { ...question, questionText: 'Rewritten question' },
        'lib-v9',
      ),
    ).toBe('both')
  })

  it('marks accepted links stale and records Assist audit-trail entries', () => {
    const { links, trail } = markStaleLinks(
      [acceptedLink()],
      [{ ...question, questionText: 'Changed wording' }],
      'lib-v1',
    )
    expect(links[0].status).toBe('stale')
    expect(trail).toHaveLength(1)
    expect(trail[0].action).toBe('marked_stale')
    expect(trail[0].reason).toBe('question_text_changed')
  })

  it('does not mark rejected links stale', () => {
    const { links, trail } = markStaleLinks(
      [acceptedLink({ status: 'rejected' })],
      [{ ...question, questionText: 'Changed' }],
      'lib-v2',
    )
    expect(links[0].status).toBe('rejected')
    expect(trail).toHaveLength(0)
  })

  it('computes re-score honesty: stale → needs Assist re-run, chips not live', () => {
    const honesty = computeRescoreHonesty(
      [acceptedLink()],
      [{ ...question, questionText: 'New text' }],
      'lib-v1',
    )
    expect(honesty.hasStaleLinks).toBe(true)
    expect(honesty.needsAssistRerun).toBe(true)
    expect(honesty.assistMapLive).toBe(false)
    expect(honesty.acceptedMultiSchemeLinks).toBe(0)
    expect(shouldPromptResuggest(honesty)).toBe(true)
  })

  it('keeps accepted links live when fingerprint and library match', () => {
    const honesty = computeRescoreHonesty([acceptedLink()], [question], 'lib-v1')
    expect(honesty.hasStaleLinks).toBe(false)
    expect(honesty.needsAssistRerun).toBe(false)
    expect(honesty.acceptedMultiSchemeLinks).toBe(1)
    expect(honesty.assistMapLive).toBe(true)
    expect(shouldPromptResuggest(honesty)).toBe(false)
  })

  it('appends assist_rerun audit-trail entries for reconfirm loop', () => {
    const fp = buildSourceFingerprint(question, 'lib-v2')
    const trail = appendAssistRerunTrail([], 'q-1', 'lib-v2', fp, '1970-01-01T00:00:00.000Z')
    expect(trail).toEqual([
      {
        action: 'assist_rerun',
        questionId: 'q-1',
        libraryVersion: 'lib-v2',
        fingerprint: fp,
        at: '1970-01-01T00:00:00.000Z',
      },
    ])
  })
})
