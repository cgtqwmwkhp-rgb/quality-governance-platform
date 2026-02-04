/**
 * Investigation Status Filter Mapping (Stage 0 Contract)
 * 
 * This file defines the mapping between UI filter labels and Repo B status values.
 * The mapping is LOCKED and covered by unit tests.
 * 
 * Repo B Status Enum:
 * - draft
 * - in_progress
 * - under_review
 * - completed
 * - closed
 * 
 * Note: "cancelled" does NOT exist in Repo B. It is explicitly disabled in UI.
 */

/**
 * Backend investigation status values (Repo B enum)
 */
export type InvestigationStatusValue = 
  | 'draft' 
  | 'in_progress' 
  | 'under_review' 
  | 'completed' 
  | 'closed';

/**
 * UI filter option configuration
 */
export interface StatusFilterOption {
  /** Unique identifier for the filter */
  id: string;
  /** Display label in UI */
  label: string;
  /** Backend status values to filter by (empty = no filter) */
  values: InvestigationStatusValue[];
  /** If true, this option is disabled in UI */
  disabled?: boolean;
  /** Tooltip to show when disabled */
  disabledTooltip?: string;
  /** CSS class for badge styling */
  badgeClass?: string;
}

/**
 * LOCKED STATUS FILTER MAPPING
 * 
 * Changes to this mapping require:
 * 1. Update unit tests
 * 2. Update Playwright E2E tests
 * 3. Document in ADR
 */
export const STATUS_FILTER_OPTIONS: StatusFilterOption[] = [
  {
    id: 'all',
    label: 'All',
    values: [], // Empty = no filter
    badgeClass: 'bg-muted text-muted-foreground',
  },
  {
    id: 'open',
    label: 'Open',
    values: ['draft', 'in_progress'], // LOCKED: Open includes draft + in_progress
    badgeClass: 'bg-blue-100 text-blue-800',
  },
  {
    id: 'in_progress',
    label: 'In Progress',
    values: ['in_progress'],
    badgeClass: 'bg-info/10 text-info',
  },
  {
    id: 'pending_review',
    label: 'Pending Review',
    values: ['under_review'],
    badgeClass: 'bg-warning/10 text-warning',
  },
  {
    id: 'completed',
    label: 'Completed',
    values: ['completed'],
    badgeClass: 'bg-success/10 text-success',
  },
  {
    id: 'closed',
    label: 'Closed',
    values: ['closed'],
    badgeClass: 'bg-muted text-muted-foreground',
  },
  {
    id: 'cancelled',
    label: 'Cancelled',
    values: [], // No backend mapping - disabled
    disabled: true,
    disabledTooltip: 'Cancelled is not supported in the current workflow',
    badgeClass: 'bg-destructive/10 text-destructive line-through',
  },
];

/**
 * Get filter option by ID
 */
export function getFilterOption(id: string): StatusFilterOption | undefined {
  return STATUS_FILTER_OPTIONS.find(opt => opt.id === id);
}

/**
 * Get enabled filter options only
 */
export function getEnabledFilterOptions(): StatusFilterOption[] {
  return STATUS_FILTER_OPTIONS.filter(opt => !opt.disabled);
}

/**
 * Get backend status values for a filter ID
 * Returns empty array for 'all' or invalid IDs
 */
export function getStatusValuesForFilter(filterId: string): InvestigationStatusValue[] {
  const option = getFilterOption(filterId);
  return option?.values ?? [];
}

/**
 * Check if a status value matches a filter
 */
export function statusMatchesFilter(
  status: InvestigationStatusValue,
  filterId: string
): boolean {
  const values = getStatusValuesForFilter(filterId);
  // 'all' filter (empty values) matches everything
  if (values.length === 0) {
    return filterId === 'all';
  }
  return values.includes(status);
}

/**
 * Status display configuration for badges
 */
export const STATUS_DISPLAY: Record<InvestigationStatusValue, { label: string; className: string }> = {
  draft: { label: 'Draft', className: 'bg-slate-100 text-slate-800' },
  in_progress: { label: 'In Progress', className: 'bg-info/10 text-info' },
  under_review: { label: 'Under Review', className: 'bg-warning/10 text-warning' },
  completed: { label: 'Completed', className: 'bg-success/10 text-success' },
  closed: { label: 'Closed', className: 'bg-muted text-muted-foreground' },
};

/**
 * Get display configuration for a status
 */
export function getStatusDisplay(status: string): { label: string; className: string } {
  const display = STATUS_DISPLAY[status as InvestigationStatusValue];
  if (display) return display;
  // Fallback for unknown statuses
  return {
    label: status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    className: 'bg-muted text-muted-foreground',
  };
}

/**
 * All valid backend status values
 */
export const ALL_STATUS_VALUES: InvestigationStatusValue[] = [
  'draft',
  'in_progress',
  'under_review',
  'completed',
  'closed',
];
