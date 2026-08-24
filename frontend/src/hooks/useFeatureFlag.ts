/**
 * useFeatureFlag - Check feature flag status
 *
 * Reads feature flags from:
 * 1. Window.__FEATURE_FLAGS__ (injected at runtime)
 * 2. localStorage overrides (for testing)
 * 3. Default values
 *
 * "Injected at runtime" was aspirational until FeatureFlagProvider existed —
 * nothing populated `window.__FEATURE_FLAGS__`, so every flag fell through to its
 * default. The provider now fills it from `GET /api/v1/meta/features` and bumps a
 * context version so mounted consumers re-read. Resolution order is unchanged,
 * and a consumer rendered outside the provider behaves exactly as it did before.
 */

import { useState, useEffect, useContext } from 'react'
import { FeatureFlagContext } from '../contexts/FeatureFlagContext'

// Feature flag definitions with defaults
const FEATURE_FLAG_DEFAULTS: Record<string, boolean> = {
  // EXP-001: Autosave for portal forms
  portal_form_autosave: false,

  // CUJ 5.4: Bow-tie UI remains hidden until backed by production data
  risk_bowtie: false,

  // Compliance Schedule (Wave 1) — opener mirrors COMPLIANCE_SCHEDULE_ENABLED
  compliance_schedule: false,

  // Wave 3 FRA / PAS79 OCR ingest — mirrors COMPLIANCE_SCHEDULE_FRA_OCR_ENABLED
  compliance_schedule_fra_ocr: false,

  // Slice 6: FRA OCR confirm → risk proposal (operator likelihood/impact)
  compliance_schedule_fra_ocr_risk: false,

  // Track C: AI regulatory-basis assist (requires CS open + this flag)
  compliance_schedule_regulatory_ai: false,

  // Doc Graph (ADR-0021) — openers mirror DOCUMENT_GRAPH_*_ENABLED settings
  document_graph: false,
  document_graph_heuristic_propose: false,
  document_graph_impact_propagation: false,
  document_graph_llm_propose: false,
  // X-0 programme flags — pre-registered default-off (later slices)
  document_graph_thread_ambient: false,
  document_graph_map_view: false,
  document_graph_dnd_propose: false,
  document_graph_structure_map: false,
  graph_coach: false,
  entity_360: false,
  entity_360_satellites: false,
  job_lifecycle: false,
  job_cell_links: false,

  // PlantEx Assist disclosure pair — mirrors AI_COPILOT_ENABLED and
  // AI_COPILOT_INFERENCE_ENABLED. Both default closed so the panel understates what
  // it is until the backend has said otherwise (see components/copilot/copilotDisclosure).
  ai_copilot: false,
  ai_copilot_inference: false,

  // FB-PR2: staff kind selector. Mirrors CUSTOMER_FEEDBACK_KINDS_ENABLED. Off until PR-5.
  customer_feedback_kinds: false,

  // Other feature flags can be added here
  portal_offline_mode: false,
  admin_ai_copilot: false,
  advanced_analytics: false,
  admin_user_management: true,
}

// Type for window augmentation
declare global {
  interface Window {
    __FEATURE_FLAGS__?: Record<string, boolean>
  }
}

/**
 * Get feature flag value with priority:
 * 1. localStorage override (for testing)
 * 2. Runtime injection
 * 3. Default value
 */
function getFeatureFlagValue(flagName: string): boolean {
  // Check localStorage override first (for testing/debugging)
  try {
    const override = localStorage.getItem(`ff_override_${flagName}`)
    if (override !== null) {
      return override === 'true'
    }
  } catch {
    // localStorage not available
  }

  // Check runtime-injected flags
  if (typeof window !== 'undefined' && window.__FEATURE_FLAGS__) {
    if (flagName in window.__FEATURE_FLAGS__) {
      return window.__FEATURE_FLAGS__[flagName]
    }
  }

  // Fall back to default
  return FEATURE_FLAG_DEFAULTS[flagName] ?? false
}

/**
 * useFeatureFlag Hook
 *
 * Returns whether a feature flag is enabled.
 * Supports localStorage overrides for testing.
 */
export function useFeatureFlag(flagName: string): boolean {
  // Only the change signal comes from context; the value still comes from
  // getFeatureFlagValue, so precedence is defined in exactly one place.
  const { version } = useContext(FeatureFlagContext)
  const [isEnabled, setIsEnabled] = useState(() => getFeatureFlagValue(flagName))

  useEffect(() => {
    // Re-check on mount in case runtime flags loaded late
    setIsEnabled(getFeatureFlagValue(flagName))

    // Listen for storage events (for cross-tab override sync)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === `ff_override_${flagName}`) {
        setIsEnabled(getFeatureFlagValue(flagName))
      }
    }

    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [flagName, version])

  return isEnabled
}

/**
 * Set a feature flag override (for testing)
 */
export function setFeatureFlagOverride(flagName: string, value: boolean): void {
  try {
    localStorage.setItem(`ff_override_${flagName}`, String(value))
    // Trigger storage event for cross-tab sync
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: `ff_override_${flagName}`,
        newValue: String(value),
      }),
    )
  } catch {
    console.warn('Failed to set feature flag override')
  }
}

/**
 * Clear a feature flag override
 */
export function clearFeatureFlagOverride(flagName: string): void {
  try {
    localStorage.removeItem(`ff_override_${flagName}`)
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: `ff_override_${flagName}`,
        newValue: null,
      }),
    )
  } catch {
    console.warn('Failed to clear feature flag override')
  }
}

export default useFeatureFlag
