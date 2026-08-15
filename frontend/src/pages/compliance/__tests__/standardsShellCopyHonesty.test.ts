import { describe, expect, it } from 'vitest'
import cy from '../../../i18n/locales/cy.json'
import en from '../../../i18n/locales/en.json'

describe('Standards shell copy honesty', () => {
  it('does not promise live graph as a future PR-B delivery', () => {
    expect(en['compliance.standards_shell.subtitle']).not.toMatch(/PR-B/)
    expect(en['compliance.standards_matrix.subtitle']).not.toMatch(/PR-B/)
    expect(cy['compliance.standards_shell.subtitle']).not.toMatch(/PR-B/)
    expect(cy['compliance.standards_matrix.subtitle']).not.toMatch(/PR-B/)
  })
})
