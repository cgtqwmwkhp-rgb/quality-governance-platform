/**
 * Standards matrix filter helpers (Wave 1 PR-A shell).
 * Live cell joins land in PR-B — this module is pure chrome/filter logic.
 * Wave 3 PR-F: shared Matrix ↔ Evidence theme presets + Evidence API bridges.
 */

export type FrameworkId =
  | '9001'
  | '14001'
  | '45001'
  | '27001'
  | '22301'
  | 'ce'
  | 'cep'
  | 'iip'
  | 'pm'
  | 'chas'
  | 'ssip'
  | 'uvdb'

export type FrameworkKind = 'standard' | 'scheme' | 'accreditation'

export type MatrixPresetId =
  | 'iso'
  | 'core'
  | 'cyber'
  | 'people'
  | 'environment'
  | 'bcp'
  | 'buyer'
  | 'all'

export interface FrameworkDef {
  id: FrameworkId
  label: string
  /** Short column header */
  shortLabel: string
  kind: FrameworkKind
  /**
   * Official home page for the standard or scheme. Required so a mislabelled
   * column is visible the moment someone checks the source (CE was Carbon Evolve).
   */
  homeUrl: string
  /** Constructionline is intentionally excluded from this catalogue. */
}

/** Programme frameworks shown in the matrix chrome (Constructionline out). */
export const STANDARDS_MATRIX_FRAMEWORKS: FrameworkDef[] = [
  {
    id: '9001',
    label: 'ISO 9001',
    shortLabel: '9001',
    kind: 'standard',
    homeUrl: 'https://www.iso.org/iso-9001-quality-management.html',
  },
  {
    id: '14001',
    label: 'ISO 14001',
    shortLabel: '14001',
    kind: 'standard',
    homeUrl: 'https://www.iso.org/iso-14001-environmental-management.html',
  },
  {
    id: '45001',
    label: 'ISO 45001',
    shortLabel: '45001',
    kind: 'standard',
    homeUrl: 'https://www.iso.org/iso-45001-occupational-health-and-safety.html',
  },
  {
    id: '27001',
    label: 'ISO 27001',
    shortLabel: '27001',
    kind: 'standard',
    homeUrl: 'https://www.iso.org/standard/82875.html',
  },
  {
    id: '22301',
    label: 'ISO 22301',
    shortLabel: '22301',
    kind: 'standard',
    homeUrl: 'https://www.iso.org/standard/75106.html',
  },
  {
    id: 'ce',
    label: 'Cyber Essentials',
    shortLabel: 'CE',
    kind: 'standard',
    homeUrl: 'https://www.ncsc.gov.uk/cyberessentials/resources',
  },
  {
    id: 'cep',
    label: 'Cyber Essentials Plus',
    shortLabel: 'CEP',
    kind: 'standard',
    homeUrl: 'https://www.ncsc.gov.uk/cyberessentials/resources',
  },
  {
    id: 'iip',
    label: 'Investors in People',
    shortLabel: 'IiP',
    kind: 'accreditation',
    homeUrl: 'https://www.investorsinpeople.com/',
  },
  {
    id: 'pm',
    label: 'Planet Mark',
    shortLabel: 'PM',
    kind: 'scheme',
    homeUrl: 'https://www.planetmark.com/',
  },
  {
    id: 'chas',
    label: 'CHAS',
    shortLabel: 'CHAS',
    kind: 'accreditation',
    homeUrl: 'https://www.chas.co.uk/',
  },
  {
    id: 'ssip',
    label: 'SSIP',
    shortLabel: 'SSIP',
    kind: 'accreditation',
    homeUrl: 'https://ssip.org.uk/',
  },
  {
    id: 'uvdb',
    label: 'UVDB',
    shortLabel: 'UVDB',
    kind: 'scheme',
    homeUrl: 'https://www.achilles.com/community/uvdb/',
  },
]

export const MATRIX_PRESET_FRAMEWORKS: Record<MatrixPresetId, FrameworkId[]> = {
  all: STANDARDS_MATRIX_FRAMEWORKS.map((f) => f.id),
  /** Full ISO family including BCP (22301). */
  iso: ['9001', '14001', '45001', '27001', '22301'],
  /** Legacy HSEQ three — kept for callers that still pass `core`. */
  core: ['9001', '14001', '45001'],
  cyber: ['27001', '22301', 'ce', 'cep'],
  people: ['iip', 'chas', 'ssip'],
  environment: ['14001', 'pm'],
  bcp: ['22301'],
  /** Awarding-body / buyer schemes — CHAS + SSIP + UVDB + Planet Mark. */
  buyer: ['chas', 'ssip', 'uvdb', 'pm'],
}

/** Theme presets shown in Matrix + Evidence chrome (legacy `core` omitted from UI). */
export const MATRIX_PRESET_IDS: MatrixPresetId[] = [
  'iso',
  'people',
  'environment',
  'bcp',
  'cyber',
  'buyer',
  'all',
]

export interface CatalogueRowLike {
  id: string
  kind?: FrameworkKind | string
  frameworkId?: FrameworkId | string
  clauseNumber?: string
  title?: string
}

/**
 * Quarantine scheme-identity shells (UVDB / Planet Mark) from the clause catalogue.
 * Rows without `kind` stay visible (honest fallback when API omits kind).
 */
export function filterClauseCatalogueRows<T extends CatalogueRowLike>(rows: T[]): T[] {
  return rows.filter((row) => {
    if (row.kind == null || row.kind === '') return true
    return row.kind !== 'scheme'
  })
}

export function resolvePresetFrameworks(preset: MatrixPresetId): FrameworkId[] {
  return [...MATRIX_PRESET_FRAMEWORKS[preset]]
}

/**
 * Intersect column filters with the active preset.
 * Empty `selected` means “all columns in preset”.
 */
export function visibleFrameworks(
  preset: MatrixPresetId,
  selected: FrameworkId[] | null | undefined,
): FrameworkDef[] {
  const presetIds = new Set(resolvePresetFrameworks(preset))
  const selectedSet = selected && selected.length > 0 ? new Set(selected) : null

  return STANDARDS_MATRIX_FRAMEWORKS.filter((fw) => {
    if (!presetIds.has(fw.id)) return false
    if (selectedSet && !selectedSet.has(fw.id)) return false
    return true
  })
}

/**
 * Bridge matrix FrameworkId → Compliance Evidence API standard id (iso9001, …).
 * Returns null when the framework has no clause-coverage API row yet.
 */
export function complianceStandardIdFromFrameworkId(id: FrameworkId): string | null {
  const map: Partial<Record<FrameworkId, string>> = {
    '9001': 'iso9001',
    '14001': 'iso14001',
    '45001': 'iso45001',
    '27001': 'iso27001',
    pm: 'planetmark',
    uvdb: 'uvdb',
  }
  return map[id] ?? null
}

/** In-app specialist homes — deep-link, do not fork SoR into Evidence. */
export const SPECIALIST_FRAMEWORK_ROUTES: Partial<Record<FrameworkId, string>> = {
  pm: '/planet-mark',
  uvdb: '/uvdb',
}

/** Map Assist / Standards `code` query (e.g. ISO9001) onto a matrix framework id. */
export function frameworkIdFromCode(code: string | null | undefined): FrameworkId | null {
  if (!code) return null
  const normalized = code.trim().toUpperCase().replace(/[^A-Z0-9]/g, '')
  const map: Record<string, FrameworkId> = {
    ISO9001: '9001',
    '9001': '9001',
    ISO14001: '14001',
    '14001': '14001',
    ISO45001: '45001',
    '45001': '45001',
    ISO27001: '27001',
    '27001': '27001',
    ISO22301: '22301',
    '22301': '22301',
    CE: 'ce',
    CEP: 'cep',
    CYBERESSENTIALS: 'ce',
    CYBERESSENTIALSPLUS: 'cep',
    IIP: 'iip',
    PM: 'pm',
    PLANETMARK: 'pm',
    CHAS: 'chas',
    SSIP: 'ssip',
    UVDB: 'uvdb',
  }
  return map[normalized] ?? null
}

export type ComplianceShellView = 'matrix' | 'evidence'

/**
 * Programme shell view from URL.
 * - `view=matrix` / `view=evidence` win
 * - Standards deep-links (`code=`) land on matrix
 * - otherwise evidence (existing CUJs / evidence centre)
 */
export function parseComplianceShellView(
  view: string | null,
  code?: string | null,
): ComplianceShellView {
  if (view === 'matrix' || view === 'evidence') return view
  if ((code || '').trim()) return 'matrix'
  return 'evidence'
}
