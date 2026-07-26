import { describe, expect, it } from 'vitest'
import { PORTAL_TEMPLATE_FALLBACK_BANNER } from '../portalTemplateHonesty'

describe('portalTemplateHonesty', () => {
  it('exposes a non-empty PX-306 fallback honesty banner outside eager i18n', () => {
    expect(PORTAL_TEMPLATE_FALLBACK_BANNER).toMatch(/No published form template/i)
    expect(PORTAL_TEMPLATE_FALLBACK_BANNER).toMatch(/built-in fallback form/i)
    expect(PORTAL_TEMPLATE_FALLBACK_BANNER.length).toBeGreaterThan(40)
  })
})
