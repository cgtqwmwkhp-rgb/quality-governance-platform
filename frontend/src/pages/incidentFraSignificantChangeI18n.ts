/** Route-chunk copy for Incident → FRA significant-change panel (kept out of shell en/cy JSON). */

export type FraSigChangeCopy = {
  title: string
  subtitle: string
  locationLabel: string
  locationPlaceholder: string
  createFra: string
  openExisting: string
  dismiss: string
  creating: string
  loadLocationsFailed: string
  createFailed: string
  createSuccess: string
  linkSuccess: string
  noLocations: string
}

const EN: FraSigChangeCopy = {
  title: 'FRA significant-change review',
  subtitle:
    'This closed incident may be a significant change. Create a site Fire Risk Assessment or open the existing one. Organisation-wide FRAs do not cover a site.',
  locationLabel: 'Premises / office',
  locationPlaceholder: 'Select a location',
  createFra: 'Create FRA',
  openExisting: 'Open existing',
  dismiss: 'Not applicable',
  creating: 'Working…',
  loadLocationsFailed: 'Could not load premises/offices.',
  createFailed: 'Could not create or open the FRA.',
  createSuccess: 'FRA obligation created',
  linkSuccess: 'Opening existing FRA',
  noLocations: 'No active premises or offices available.',
}

const CY: FraSigChangeCopy = {
  title: 'Adolygiad newid sylweddol FRA',
  subtitle:
    'Gallai’r digwyddiad caeedig hwn fod yn newid sylweddol. Creu Asesiad Risg Tân safle neu agor yr un sydd eisoes. Nid yw FRA sefydliad-eang yn cwmpasu safle.',
  locationLabel: 'Adeilad / swyddfa',
  locationPlaceholder: 'Dewiswch leoliad',
  createFra: 'Creu FRA',
  openExisting: 'Agor sydd eisoes',
  dismiss: 'Ddim yn berthnasol',
  creating: 'Yn gweithio…',
  loadLocationsFailed: 'Methu llwytho adeiladau/swyddfeydd.',
  createFailed: 'Methu creu neu agor yr FRA.',
  createSuccess: 'Rhwymedigaeth FRA wedi’i chreu',
  linkSuccess: 'Yn agor FRA sydd eisoes',
  noLocations: 'Dim adeiladau na swyddfeydd gweithredol ar gael.',
}

export function fraSigChangeCopy(lang: string | undefined): FraSigChangeCopy {
  return (lang || 'en').toLowerCase().startsWith('cy') ? CY : EN
}
