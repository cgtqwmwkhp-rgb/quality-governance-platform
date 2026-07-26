/** Scope labels for Analytics Total/Open/Closed columns (PX-226). */

export type ModuleScope = 'register' | 'period'

export function scopeLabel(scope: ModuleScope): string {
  return scope === 'register' ? 'Register' : 'Period'
}

export function scopeCaption(periodLabel: string): string {
  return (
    `Total, Open and Closed are register-wide unless the Scope column says otherwise. ` +
    `Distribution and “in period” figures use the selected ${periodLabel}.`
  )
}
