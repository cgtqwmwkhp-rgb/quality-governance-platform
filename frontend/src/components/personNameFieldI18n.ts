/** Chunked copy for PersonNameField (kept out of shell en/cy JSON). */

export type PersonNameFieldCopy = {
  placeholder: string
  loading: string
  loadFailed: string
  noEmployees: string
  useFreeText: string
  selectedEmployee: string
  freeTextHint: string
  clear: string
}

const EN: PersonNameFieldCopy = {
  placeholder: 'Search employees…',
  loading: 'Loading employees…',
  loadFailed: 'Could not load employees. Try again, or type a name.',
  noEmployees: 'No employees found',
  useFreeText: 'Use “{name}” as typed name',
  selectedEmployee: 'Linked employee',
  freeTextHint: 'Typed name (not linked to an employee)',
  clear: 'Clear',
}

const CY: PersonNameFieldCopy = {
  placeholder: 'Chwilio gweithwyr…',
  loading: 'Yn llwytho gweithwyr…',
  loadFailed: 'Methu llwytho gweithwyr. Ceisiwch eto, neu teipiwch enw.',
  noEmployees: 'Dim gweithwyr wedi’u canfod',
  useFreeText: 'Defnyddio “{name}” fel enw wedi’i deipio',
  selectedEmployee: 'Gweithiwr cysylltiedig',
  freeTextHint: 'Enw wedi’i deipio (heb gysylltu â gweithiwr)',
  clear: 'Clirio',
}

export function personNameFieldCopy(lang: string | undefined): PersonNameFieldCopy {
  return (lang || 'en').toLowerCase().startsWith('cy') ? CY : EN
}

export function formatPersonNameCopy(template: string, name: string): string {
  return template.replace('{name}', name)
}
