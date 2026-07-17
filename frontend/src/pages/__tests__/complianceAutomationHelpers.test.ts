import { describe, expect, it } from 'vitest'
import { formatStandardCode, scoreBarColor } from '../complianceAutomationHelpers'

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
})
