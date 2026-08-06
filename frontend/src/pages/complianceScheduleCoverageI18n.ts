/** Route-chunk copy for FRA/drill coverage panel (kept out of shell en/cy JSON). */

export type CoverageCopy = {
  title: string
  subtitle: string
  locations: string
  missingFra: string
  missingDrill: string
  missingBoth: string
  emptyLocations: string
  gapFra: string
  okFra: string
  gapDrill: string
  okDrill: string
}

const EN: CoverageCopy = {
  title: 'FRA / fire-drill coverage',
  subtitle:
    'Active premises/offices without a site-scoped FRA or fire drill. Org-wide rows do not cover a site.',
  locations: 'Locations',
  missingFra: 'Missing FRA',
  missingDrill: 'Missing drill',
  missingBoth: 'Missing both',
  emptyLocations: 'No premises/offices in scope.',
  gapFra: 'No FRA',
  okFra: 'FRA ok',
  gapDrill: 'No drill',
  okDrill: 'Drill ok',
}

const CY: CoverageCopy = {
  title: 'Cwmpas FRA / ymarfer tan',
  subtitle:
    'Adeiladau/swyddfeydd heb FRA neu ymarfer tan ar lefel safle. Nid yw rhesi sefydliad-eang yn cwmpasu safle.',
  locations: 'Lleoliadau',
  missingFra: 'FRA ar goll',
  missingDrill: 'Ymarfer ar goll',
  missingBoth: 'Y ddau ar goll',
  emptyLocations: 'Dim adeiladau/swyddfeydd yn y cwmpas.',
  gapFra: 'Dim FRA',
  okFra: 'FRA ok',
  gapDrill: 'Dim ymarfer',
  okDrill: 'Ymarfer ok',
}

export function coverageCopy(lang: string | undefined): CoverageCopy {
  return (lang || 'en').toLowerCase().startsWith('cy') ? CY : EN
}
