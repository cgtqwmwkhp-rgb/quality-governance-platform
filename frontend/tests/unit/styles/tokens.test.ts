import { spacing, typography, colors } from '@/styles/tokens';

describe('Design Tokens', () => {
  it('has spacing scale', () => {
    expect(spacing.xs).toBeDefined();
    expect(spacing.sm).toBeDefined();
    expect(spacing.md).toBeDefined();
    expect(spacing.lg).toBeDefined();
    expect(spacing.xl).toBeDefined();
  });

  it('has typography', () => {
    expect(typography.fontFamily.sans).toBeDefined();
    expect(typography.fontSize.base).toBeDefined();
  });

  it('has color palette', () => {
    expect(colors.primary[500]).toBeDefined();
    expect(colors.success[500]).toBeDefined();
    expect(colors.danger[500]).toBeDefined();
    expect(colors.neutral[500]).toBeDefined();
  });
});
