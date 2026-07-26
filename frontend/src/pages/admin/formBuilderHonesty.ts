/** Honesty copy when Form Builder inventory diverges from live intake (PX-186 / PX-272). */

export interface FormBuilderCountHonesty {
  /** Primary stat label shown on the admin dashboard tile. */
  label: string
  /** Secondary line under the count — must not claim “healthy zero forms in service”. */
  change: string
  /** True when a zero builder count must not be read as “no forms in production”. */
  zeroIsNotAbsenceOfLiveForms: boolean
}

export function buildActiveFormsStatHonesty(builderTotal: number | null): FormBuilderCountHonesty {
  if (builderTotal === null) {
    return {
      label: 'Active Forms',
      change: 'Count unavailable',
      zeroIsNotAbsenceOfLiveForms: false,
    }
  }
  if (builderTotal === 0) {
    return {
      label: 'Form Builder templates',
      change:
        'Builder has 0 templates — live portal intake forms are not managed here',
      zeroIsNotAbsenceOfLiveForms: true,
    }
  }
  return {
    label: 'Active Forms',
    change: 'Live from Form Builder API',
    zeroIsNotAbsenceOfLiveForms: false,
  }
}

export function formBuilderEmptyStateCopy(options: {
  hasSearchOrFilter: boolean
}): { title: string; body: string } {
  if (options.hasSearchOrFilter) {
    return {
      title: 'No forms found',
      body: 'Try adjusting your search or filters',
    }
  }
  return {
    title: 'No Form Builder templates',
    body:
      'The Form Builder catalogue is empty. Live portal intake forms (incident, near miss, complaint, RTA, and related) are served outside this catalogue — creating a template here does not automatically govern those live forms.',
  }
}
