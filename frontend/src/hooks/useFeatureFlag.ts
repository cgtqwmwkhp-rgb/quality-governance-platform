/**
 * useFeatureFlag - Check feature flag status
 *
 * Reads feature flags from:
 * 1. Window.__FEATURE_FLAGS__ (injected at runtime)
 * 2. localStorage overrides (for testing)
 * 3. Default values
 */

import { useState, useEffect } from "react";

// Feature flag definitions with defaults
const FEATURE_FLAG_DEFAULTS: Record<string, boolean> = {
  // EXP-001: Autosave for portal forms
  portal_form_autosave: false,

  // Other feature flags can be added here
  portal_offline_mode: false,
  admin_ai_copilot: false,
  advanced_analytics: false,
};

// Type for window augmentation
declare global {
  interface Window {
    __FEATURE_FLAGS__?: Record<string, boolean>;
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
    const override = localStorage.getItem(`ff_override_${flagName}`);
    if (override !== null) {
      return override === "true";
    }
  } catch {
    // localStorage not available
  }

  // Check runtime-injected flags
  if (typeof window !== "undefined" && window.__FEATURE_FLAGS__) {
    if (flagName in window.__FEATURE_FLAGS__) {
      return window.__FEATURE_FLAGS__[flagName] ?? false;
    }
  }

  // Fall back to default
  return FEATURE_FLAG_DEFAULTS[flagName] ?? false;
}

/**
 * useFeatureFlag Hook
 *
 * Returns whether a feature flag is enabled.
 * Supports localStorage overrides for testing.
 */
export function useFeatureFlag(flagName: string): boolean {
  const [isEnabled, setIsEnabled] = useState(() =>
    getFeatureFlagValue(flagName),
  );

  useEffect(() => {
    // Re-check on mount in case runtime flags loaded late
    setIsEnabled(getFeatureFlagValue(flagName));

    // Listen for storage events (for cross-tab override sync)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === `ff_override_${flagName}`) {
        setIsEnabled(getFeatureFlagValue(flagName));
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [flagName]);

  return isEnabled;
}

/**
 * Set a feature flag override (for testing)
 */
export function setFeatureFlagOverride(flagName: string, value: boolean): void {
  try {
    localStorage.setItem(`ff_override_${flagName}`, String(value));
    // Trigger storage event for cross-tab sync
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: `ff_override_${flagName}`,
        newValue: String(value),
      }),
    );
  } catch {
    console.warn("Failed to set feature flag override");
  }
}

/**
 * Clear a feature flag override
 */
export function clearFeatureFlagOverride(flagName: string): void {
  try {
    localStorage.removeItem(`ff_override_${flagName}`);
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: `ff_override_${flagName}`,
        newValue: null,
      }),
    );
  } catch {
    console.warn("Failed to clear feature flag override");
  }
}

export default useFeatureFlag;
