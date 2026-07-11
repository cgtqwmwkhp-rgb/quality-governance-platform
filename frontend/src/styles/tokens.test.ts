import { describe, expect, it } from 'vitest'
import { colors, spacing, typography } from './tokens'

describe('design tokens', () => {
  it('exposes spacing scale', () => {
    expect(spacing.xs).toBe('0.25rem')
    expect(spacing.sm).toBe('0.5rem')
    expect(spacing.md).toBe('1rem')
    expect(spacing.lg).toBe('1.5rem')
    expect(spacing.xl).toBe('2rem')
    expect(spacing['2xl']).toBe('3rem')
  })

  it('exposes typography fonts and sizes', () => {
    expect(typography.fontFamily.sans).toMatch(/Inter/)
    expect(typography.fontFamily.mono).toMatch(/JetBrains/)
    expect(typography.fontSize.xs).toBe('0.75rem')
    expect(typography.fontSize.sm).toBe('0.875rem')
    expect(typography.fontSize.base).toBe('1rem')
    expect(typography.fontSize.lg).toBe('1.125rem')
    expect(typography.fontSize.xl).toBe('1.25rem')
    expect(typography.fontSize['2xl']).toBe('1.5rem')
    expect(typography.fontSize['3xl']).toBe('1.875rem')
  })

  it('exposes semantic color palettes', () => {
    expect(colors.primary[50]).toMatch(/^#/)
    expect(colors.primary[500]).toMatch(/^#/)
    expect(colors.primary[700]).toMatch(/^#/)
    expect(colors.primary[900]).toMatch(/^#/)
    expect(colors.success[500]).toMatch(/^#/)
    expect(colors.warning[500]).toMatch(/^#/)
    expect(colors.danger[700]).toMatch(/^#/)
    expect(colors.neutral[50]).toMatch(/^#/)
    expect(colors.neutral[100]).toMatch(/^#/)
    expect(colors.neutral[200]).toMatch(/^#/)
    expect(colors.neutral[500]).toMatch(/^#/)
    expect(colors.neutral[700]).toMatch(/^#/)
    expect(colors.neutral[900]).toMatch(/^#/)
  })
})
