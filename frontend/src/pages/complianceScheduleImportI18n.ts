/** Route-chunk copy for CS CSV import (kept out of shell en/cy JSON). */

export type ImportCopy = {
  button: string
  title: string
  subtitle: string
  dryRun: string
  commit: string
  cancel: string
  creates: string
  errors: string
  emptyFile: string
  success: string
  blocked: string
}

const EN: ImportCopy = {
  button: 'Import CSV',
  title: 'Import obligations',
  subtitle:
    'CSV columns: template_key, location_id (or location_name). Activates catalogue rows per site — org-wide not allowed.',
  dryRun: 'Validate',
  commit: 'Commit',
  cancel: 'Cancel',
  creates: 'Creates',
  errors: 'Errors',
  emptyFile: 'Choose a CSV file first.',
  success: 'Import committed',
  blocked: 'Fix row errors before commit.',
}

const CY: ImportCopy = {
  button: 'Mewnforio CSV',
  title: 'Mewnforio rhwymedigaethau',
  subtitle:
    'Colofnau CSV: template_key, location_id (neu location_name). Yn actifadu rhesi catalog fesul safle — dim sefydliad-eang.',
  dryRun: 'Dilysu',
  commit: 'Cyflwyno',
  cancel: 'Canslo',
  creates: 'Creu',
  errors: 'Gwallau',
  emptyFile: 'Dewiswch ffeil CSV yn gyntaf.',
  success: 'Mewnforio wedi ei gyflwyno',
  blocked: 'Trwsiwch wallau rhes cyn cyflwyno.',
}

export function importCopy(lang: string | undefined): ImportCopy {
  return (lang || 'en').toLowerCase().startsWith('cy') ? CY : EN
}
