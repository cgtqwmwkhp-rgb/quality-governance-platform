import { describe, expect, it } from 'vitest'
import {
  WORKFORCE_ROLE_CODE_HINTS,
  WORKFORCE_ROLES_LOOKUP_CATEGORY,
  workforceRoleHintCodes,
} from '../workforceRolesCatalog'

describe('workforceRolesCatalog', () => {
  it('documents the workforce_roles lookup category key', () => {
    expect(WORKFORCE_ROLES_LOOKUP_CATEGORY).toBe('workforce_roles')
  })

  it('lists standard role codes without fabricating labels as configured data', () => {
    expect(WORKFORCE_ROLE_CODE_HINTS.map((h) => h.code)).toEqual([
      'engineer',
      'field_engineer',
      'supervisor',
      'process_scheduler',
    ])
    expect(workforceRoleHintCodes()).toBe(
      'engineer, field_engineer, supervisor, process_scheduler',
    )
  })
})
