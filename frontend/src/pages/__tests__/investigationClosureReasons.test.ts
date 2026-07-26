/**
 * PX-134: the closure checklist rendered "MISSING REQUIRED SECTION" raw, which
 * told the user nothing about which section blocked closure.
 */
import { describe, expect, it } from 'vitest'
import { describeClosureBlockers, describeCompletionBlockers, isOnlyOpenActionsBlocking } from '../investigationClosureReasons'

/** Stand-in for i18next's `t(key, defaultValue, options)`. */
const t = (_key: string, fallback: string, options?: Record<string, unknown>) =>
  fallback.replace(/\{\{(\w+)\}\}/g, (_match, name) => String(options?.[name] ?? ''))

describe('describeClosureBlockers', () => {
  it('names the section behind MISSING_REQUIRED_SECTION', () => {
    const lines = describeClosureBlockers(
      {
        reasons: ['MISSING_REQUIRED_SECTION'],
        missing_items: [
          {
            code: 'MISSING_REQUIRED_SECTION',
            section_key: 'sec_root_cause',
            section_label: 'Root cause analysis',
            path: 'sec_root_cause',
          },
        ],
      },
      t,
    )

    expect(lines).toHaveLength(1)
    expect(lines[0].text).toContain('Root cause analysis')
    expect(lines[0].text).not.toMatch(/MISSING/i)
    expect(lines[0].sectionKey).toBe('sec_root_cause')
  })

  it('names both the field and its section for MISSING_REQUIRED_FIELD', () => {
    const [line] = describeClosureBlockers(
      {
        reasons: ['MISSING_REQUIRED_FIELD'],
        missing_items: [
          {
            code: 'MISSING_REQUIRED_FIELD',
            section_key: 'sec_findings',
            section_label: 'Findings',
            field_key: 'immediate_cause',
            field_label: 'Immediate cause',
            path: 'sec_findings.immediate_cause',
          },
        ],
      },
      t,
    )

    expect(line.text).toContain('Immediate cause')
    expect(line.text).toContain('Findings')
  })

  it('expands one reason code into one line per named blocker', () => {
    const lines = describeClosureBlockers(
      {
        reasons: ['MISSING_REQUIRED_FIELD'],
        missing_items: [
          {
            code: 'MISSING_REQUIRED_FIELD',
            section_key: 's1',
            section_label: 'Section one',
            field_key: 'a',
            field_label: 'Field A',
            path: 's1.a',
          },
          {
            code: 'MISSING_REQUIRED_FIELD',
            section_key: 's1',
            section_label: 'Section one',
            field_key: 'b',
            field_label: 'Field B',
            path: 's1.b',
          },
        ],
      },
      t,
    )

    expect(lines.map((line) => line.id)).toEqual([
      'MISSING_REQUIRED_FIELD:s1.a',
      'MISSING_REQUIRED_FIELD:s1.b',
    ])
  })

  it('still explains a code the backend could not name, without shouting it', () => {
    const [line] = describeClosureBlockers(
      { reasons: ['MISSING_REQUIRED_SECTION'], missing_items: [] },
      t,
    )
    expect(line.text).not.toMatch(/MISSING_REQUIRED_SECTION/)
    expect(line.text).toMatch(/required template section/i)
  })

  it('keeps the existing wording for open actions and other known codes', () => {
    const lines = describeClosureBlockers(
      { reasons: ['OPEN_ACTIONS_REMAIN', 'LEVEL_NOT_SET', 'STATUS_NOT_COMPLETE'] },
      t,
    )
    expect(lines[0].text).toMatch(/Open CAPA\/actions/)
    expect(lines[1].text).toMatch(/investigation level/)
    expect(lines[2].text).toMatch(/Completed/)
  })

  it('humanises an unknown code rather than rendering raw SCREAMING_CASE', () => {
    const [line] = describeClosureBlockers({ reasons: ['SOME_NEW_GATE'] }, t)
    expect(line.text).toBe('Some new gate')
  })

  it('names completion blockers from completion_reasons', () => {
    const lines = describeCompletionBlockers(
      {
        completion_reasons: ['MISSING_FINDINGS'],
        missing_items: [
          {
            code: 'MISSING_FINDINGS',
            section_key: 'summary',
            section_label: 'Summary',
            field_key: 'findings',
            field_label: 'Findings',
            path: 'summary.findings',
          },
        ],
      },
      t,
    )
    expect(lines[0].text).toContain('Findings')
  })

  it('detects when only open actions block completion', () => {
    expect(isOnlyOpenActionsBlocking(['OPEN_ACTIONS_REMAIN'])).toBe(true)
    expect(isOnlyOpenActionsBlocking(['OPEN_ACTIONS_REMAIN', 'MISSING_FINDINGS'])).toBe(false)
  })

  it('returns nothing when the investigation is ready to close', () => {
    expect(describeClosureBlockers({ reasons: [] }, t)).toEqual([])
  })

  it('does not duplicate a reason code that the backend listed twice', () => {
    const lines = describeClosureBlockers({ reasons: ['LEVEL_NOT_SET', 'LEVEL_NOT_SET'] }, t)
    expect(lines).toHaveLength(1)
  })
})
