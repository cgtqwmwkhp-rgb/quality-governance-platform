import { describe, expect, it } from 'vitest'
import {
  INCIDENT_CLIENT_ONLY_PARAMS,
  INCIDENT_SERVER_FILTERABLE_PARAMS,
} from '../incidentServerFilterableParams'

describe('incident SERVER_FILTERABLE_PARAMS', () => {
  it('does not treat client status/severity as SQL totals', () => {
    expect(INCIDENT_SERVER_FILTERABLE_PARAMS).toContain('type')
    expect(INCIDENT_SERVER_FILTERABLE_PARAMS).not.toContain('status')
    expect(INCIDENT_SERVER_FILTERABLE_PARAMS).not.toContain('severity')
    for (const name of INCIDENT_CLIENT_ONLY_PARAMS) {
      expect(INCIDENT_SERVER_FILTERABLE_PARAMS).not.toContain(name)
    }
  })
})
