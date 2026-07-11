import { describe, expect, it } from 'vitest'
import { colors, spacing, typography } from './tokens'

describe('design tokens', () => {
  it('exposes spacing scale', () => {
    expect(spacing.md).toBe('1rem')
    expect(spacing.xl).toBe('2rem')
  })

  it('exposes typography fonts and sizes', () => {
    expect(typography.fontFamily.sans).toMatch(/Inter/)
    expect(typography.fontSize.base).toBe('1rem')
  })

  it('exposes semantic color palettes', () => {
    expect(colors.primary[500]).toMatch(/^#/)
    expect(colors.danger[700]).toMatch(/^#/)
    expect(colors.neutral[900]).toMatch(/^#/)
  })
})
