import { decodeHtmlEntities } from '../helpers/utils'

/** Decode legacy HTML-entity storage for incident text fields (PX-009). */
export function displayIncidentText(value: unknown): string {
  if (value == null || value === '') return ''
  return decodeHtmlEntities(String(value))
}
