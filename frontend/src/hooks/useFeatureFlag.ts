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

  // Track C: AI regulatory-basis assist (requires CS open + this flag)
  compliance_schedule_regulatory_ai: false,

  // Doc Graph (ADR-0021) — openers mirror DOCUMENT_GRAPH_*_ENABLED settings
  document_graph: false,
  document_graph_heuristic_propose: false,
  document_graph_impact_propagation: false,
  document_graph_llm_propose: false,

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
