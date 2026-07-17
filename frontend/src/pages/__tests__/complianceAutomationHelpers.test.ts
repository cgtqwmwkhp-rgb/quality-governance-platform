import { describe, expect, it } from 'vitest'
import type { AuditRun } from '../../api/client'
import {
  buildAuditRunWorkspacePath,
  countOverdueMonitoringRuns,
  deriveMonitoringAuditRunStatus,
  formatStandardCode,
  mapRunsToMonitoringRows,
  MONITORING_AUDITS_HANDOFF_PATH,
  scoreBarColor,
} from '../complianceAutomationHelpers'

function makeRun(overrides: Partial<AuditRun> = {}): AuditRun {
  return {
    id: 1,
    reference_number: 'AUD-001',
    template_id: 10,
    template_version: 1,
    status: 'scheduled',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('complianceAutomationHelpers', () => {
  describe('formatStandardCode', () => {
    it('maps known ISO codes to spaced labels', () => {
      expect(formatStandardCode('ISO9001')).toBe('ISO 9001')
      expect(formatStandardCode('ISO45001')).toBe('ISO 45001')
    })

    it('formats unknown codes with a space before digits', () => {
      expect(formatStandardCode('ISO50001')).toBe('ISO 50001')
    })
  })

  describe('scoreBarColor', () => {
    it('returns success for high scores', () => {
      expect(scoreBarColor(80)).toBe('bg-success')
      expect(scoreBarColor(95)).toBe('bg-success')
    })

    it('returns info for mid scores', () => {
      expect(scoreBarColor(60)).toBe('bg-info')
      expect(scoreBarColor(79)).toBe('bg-info')
    })

    it('returns primary for low scores', () => {
      expect(scoreBarColor(59)).toBe('bg-primary')
      expect(scoreBarColor(0)).toBe('bg-primary')
    })
  })

  describe('audits handoff (CA-W1b)', () => {
    it('exports authoritative Audits module handoff path', () => {
      expect(MONITORING_AUDITS_HANDOFF_PATH).toBe('/audits?view=kanban')
    })

    it('builds execute path for standard runs', () => {
      expect(buildAuditRunWorkspacePath(makeRun())).toBe('/audits/1/execute')
    })

    it('builds import-review path for external import runs', () => {
      expect(
        buildAuditRunWorkspacePath(makeRun({ is_external_audit_import: true })),
      ).toBe('/audits/1/import-review')
    })

    it('derives overdue when scheduled date is in the past', () => {
      const now = new Date('2026-07-01T12:00:00Z')
      expect(
        deriveMonitoringAuditRunStatus(
          makeRun({ scheduled_date: '2026-06-01', status: 'scheduled' }),
          now,
        ),
      ).toBe('overdue')
    })

    it('ignores completed and draft runs for monitoring rows', () => {
      const rows = mapRunsToMonitoringRows([
        makeRun({ id: 1, status: 'completed' }),
        makeRun({ id: 2, status: 'draft' }),
        makeRun({ id: 3, status: 'in_progress', title: 'Site walk' }),
      ])
      expect(rows).toHaveLength(1)
      expect(rows[0]?.id).toBe(3)
      expect(rows[0]?.status).toBe('in_progress')
    })

    it('counts overdue rows for KPI badge', () => {
      const now = new Date('2026-07-01T12:00:00Z')
      const rows = mapRunsToMonitoringRows(
        [
          makeRun({ id: 1, scheduled_date: '2026-06-01', status: 'scheduled' }),
          makeRun({ id: 2, scheduled_date: '2026-08-01', status: 'scheduled' }),
        ],
        now,
      )
      expect(countOverdueMonitoringRuns(rows)).toBe(1)
    })
  })
})
