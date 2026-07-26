import { describe, expect, it } from 'vitest'
import {
  brandingLooksUnset,
  buildSettingDefinitions,
  colorInputDisplayValue,
  isColorUnset,
  mergeSettingsFromApi,
  supportContactUnset,
} from '../systemSettingsHelpers'

describe('systemSettingsHelpers', () => {
  it('does not default branding colours to black (PX-227)', () => {
    const defs = buildSettingDefinitions()
    expect(defs.find((d) => d.key === 'primary_color')?.value).toBe('')
    expect(defs.find((d) => d.key === 'accent_color')?.value).toBe('')
    expect(isColorUnset('')).toBe(true)
    expect(isColorUnset('#000000')).toBe(true)
    expect(colorInputDisplayValue('')).toBe('#ffffff')
  })

  it('merges API values over templates', () => {
    const merged = mergeSettingsFromApi(buildSettingDefinitions(), [
      { key: 'company_name', value: 'Plantexpand Limited' },
      { key: 'primary_color', value: '#0B6E4F' },
    ])
    expect(merged.find((s) => s.key === 'company_name')?.value).toBe('Plantexpand Limited')
    expect(merged.find((s) => s.key === 'primary_color')?.value).toBe('#0B6E4F')
    expect(brandingLooksUnset(merged)).toBe(false)
  })

  it('detects unset branding and support contact', () => {
    const empty = buildSettingDefinitions()
    expect(brandingLooksUnset(empty)).toBe(true)
    expect(supportContactUnset(empty)).toBe(true)
  })

  it('uses select options for regional keys (PX-229)', () => {
    const defs = buildSettingDefinitions()
    for (const key of ['date_format', 'timezone', 'language']) {
      const row = defs.find((d) => d.key === key)
      expect(row?.value_type).toBe('select')
      expect(row?.select_options?.length).toBeGreaterThan(0)
    }
  })
})
