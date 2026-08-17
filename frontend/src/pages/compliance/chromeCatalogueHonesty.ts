import type { ComplianceEvidenceSectionId } from '../complianceEvidenceHelpers'
import type { FrameworkId } from './standardsMatrixFilters'
import { SPECIALIST_FRAMEWORK_ROUTES } from './standardsMatrixFilters'

/** Frameworks on the Evidence chrome that have no clause-coverage API row. */
export const CHROME_WITHOUT_CLAUSE_CATALOGUE = ['chas', 'ssip', 'pm', 'uvdb'] as const

export type ChromeWithoutClauseCatalogue = (typeof CHROME_WITHOUT_CLAUSE_CATALOGUE)[number]

export function isChromeWithoutClauseCatalogue(
  id: string | undefined,
): id is ChromeWithoutClauseCatalogue {
  return (
    id === 'chas' || id === 'ssip' || id === 'pm' || id === 'uvdb'
  )
}

export function chromeHonestyKind(
  id: string | undefined,
): 'specialist' | 'provisional' | null {
  if (id === 'pm' || id === 'uvdb') return 'specialist'
  if (id === 'chas' || id === 'ssip') return 'provisional'
  return null
}

export function chromeProgramLabel(id: ChromeWithoutClauseCatalogue): string {
  switch (id) {
    case 'pm':
      return 'Planet Mark'
    case 'uvdb':
      return 'UVDB'
    case 'chas':
      return 'CHAS'
    case 'ssip':
      return 'SSIP'
  }
}

export type ChromeHonestyCopy = {
  title: string
  titleKey: string
  description: string
  descriptionKey: string
}

/**
 * Same four Evidence tabs as ISO / CE / IiP. Body copy must not invent a tree,
 * a coverage %, or “no gaps”.
 */
export function chromeEvidenceHonesty(
  frameworkId: ChromeWithoutClauseCatalogue,
  section: ComplianceEvidenceSectionId,
): ChromeHonestyCopy {
  const program = chromeProgramLabel(frameworkId)
  const kind = chromeHonestyKind(frameworkId)
  const specialist = kind === 'specialist'

  if (section === 'clauses') {
    return specialist
      ? {
          title: `No ${program} clause tree on this page`,
          titleKey: 'compliance.evidence.chrome.clauses.specialist_title',
          description: `${program} is a specialist programme. Clauses are not inherited into this catalogue. Open the dedicated workspace. Full/Partial/Gaps are not invented here.`,
          descriptionKey: 'compliance.evidence.chrome.clauses.specialist_description',
        }
      : {
          title: `No ${program} clause tree yet`,
          titleKey: 'compliance.evidence.chrome.clauses.provisional_title',
          description: `${program} is not in the clause evidence catalogue yet. Matrix alignment and the cert shelf still apply. Full/Partial/Gaps are not invented.`,
          descriptionKey: 'compliance.evidence.chrome.clauses.provisional_description',
        }
  }

  if (section === 'evidence') {
    return {
      title: `No ${program} clause-linked evidence`,
      titleKey: 'compliance.evidence.chrome.evidence.title',
      description: specialist
        ? `Evidence for ${program} is not scored as clause Full/Partial/Gaps here. Use the specialist workspace.`
        : `${program} has no clause-linked evidence list until a publisher-pinned catalogue exists.`,
      descriptionKey: specialist
        ? 'compliance.evidence.chrome.evidence.specialist_description'
        : 'compliance.evidence.chrome.evidence.provisional_description',
    }
  }

  if (section === 'gaps') {
    return {
      title: `${program} is not a clause gap score`,
      titleKey: 'compliance.evidence.chrome.gaps.title',
      description:
        'Gap Analysis needs a clause catalogue. This is not zero gaps and not 100% covered.',
      descriptionKey: 'compliance.evidence.chrome.gaps.description',
    }
  }

  return {
    title: `No imported ${program} audits on this page`,
    titleKey: 'compliance.evidence.chrome.imported.title',
    description: specialist
      ? `Imports for ${program} appear here when the scheme matches. Otherwise use the specialist workspace.`
      : `No ${program} imports on the loaded page. This is not an ISO audit list.`,
    descriptionKey: specialist
      ? 'compliance.evidence.chrome.imported.specialist_description'
      : 'compliance.evidence.chrome.imported.provisional_description',
  }
}

export function chromeSpecialistRoute(id: FrameworkId): string | undefined {
  return SPECIALIST_FRAMEWORK_ROUTES[id]
}

/** Exact scheme keys only — no fuzzy name join. */
export function importedRecordMatchesChrome(
  scheme: string | null | undefined,
  frameworkId: ChromeWithoutClauseCatalogue,
): boolean {
  const n = (scheme || '').trim().toLowerCase()
  if (frameworkId === 'pm') return n === 'planet_mark'
  if (frameworkId === 'uvdb') return n === 'uvdb'
  if (frameworkId === 'chas') return n === 'chas'
  if (frameworkId === 'ssip') return n === 'ssip'
  return false
}

/** Do not send CHAS/SSIP/PM/UVDB ids to the clause-coverage APIs. */
export function clauseCatalogueApiFilter(
  selectedStandard: string | 'all',
): string | undefined {
  if (selectedStandard === 'all') return undefined
  if (isChromeWithoutClauseCatalogue(selectedStandard)) return undefined
  return selectedStandard
}
