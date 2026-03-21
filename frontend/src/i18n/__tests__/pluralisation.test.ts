import { createInstance } from 'i18next'
import { beforeAll, describe, expect, it } from 'vitest'

describe('i18next pluralisation', () => {
  const i18n = createInstance()

  beforeAll(async () => {
    await i18n.init({
      lng: 'en',
      fallbackLng: 'en',
      pluralSeparator: '_',
      interpolation: { escapeValue: false },
      resources: {
        en: {
          translation: {
            item_one: '{{count}} item',
            item_other: '{{count}} items',
          },
        },
      },
    })
  })

  it('uses singular form when count is 1', () => {
    expect(i18n.t('item', { count: 1 })).toBe('1 item')
  })

  it('uses plural form when count is greater than 1', () => {
    expect(i18n.t('item', { count: 5 })).toBe('5 items')
  })

  it('uses plural (other) form when count is 0', () => {
    expect(i18n.t('item', { count: 0 })).toBe('0 items')
  })
})
