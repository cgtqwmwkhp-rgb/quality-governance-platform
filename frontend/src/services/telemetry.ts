/**
 * Telemetry Service for EXP-001 and future experiments
 *
 * Emits events to:
 * 1. Backend API (for server-side aggregation)
 * 2. Console (for staging/development debugging only)
 * 3. LocalStorage buffer (for offline resilience)
 *
 * NO PII POLICY:
 * - All dimensions must be bounded (enums, not free text)
 * - No user IDs, emails, names, or identifiable data
 * - Form content is NOT captured, only metadata
 *
 * QUARANTINE POLICY (ADR-0004):
 * - Telemetry failures MUST NOT block user workflows
 * - Telemetry failures MUST NOT spam console with errors
 * - TELEMETRY_ENABLED flag controls API calls (default: enabled in dev/staging, disabled in prod)
 */

import { API_BASE_URL } from "../config/apiBase";

// Environment detection
const IS_PRODUCTION =
  window.location.hostname.includes("azurewebsites.net") &&
  !window.location.hostname.includes("staging");
const IS_STAGING =
  window.location.hostname.includes("staging") ||
  window.location.hostname === "localhost";
const IS_DEVELOPMENT = window.location.hostname === "localhost";

// === TELEMETRY FEATURE FLAG (ADR-0004) ===
// Disabled in production until CORS is confirmed working.
// Enable by setting window.__TELEMETRY_ENABLED__ = true in console or config.
const TELEMETRY_ENABLED = (() => {
  // Check for explicit override
  if (
    typeof (window as unknown as { __TELEMETRY_ENABLED__?: boolean })
      .__TELEMETRY_ENABLED__ === "boolean"
  ) {
    return (window as unknown as { __TELEMETRY_ENABLED__?: boolean })
      .__TELEMETRY_ENABLED__;
  }
  // Default: enabled in dev/staging, DISABLED in production (CORS quarantine)
  return !IS_PRODUCTION;
})();

// Event buffer for offline resilience
const EVENT_BUFFER_KEY = "exp_telemetry_buffer";
const MAX_BUFFER_SIZE = 100;

// === SILENT LOGGING (NO CONSOLE SPAM) ===
// Only log in development, never in staging/production
const silentLog = IS_DEVELOPMENT
  ? (...args: unknown[]) => console.log("[Telemetry]", ...args)
  : () => {}; // No-op in staging/production

// ============================================================================
// Types
// ============================================================================

interface TelemetryEvent {
  name: string;
  timestamp: string;
  sessionId: string;
  dimensions: Record<string, string | number | boolean>;
}

interface ExpEventDimensions {
  formType?: string;
  flagEnabled?: boolean;
  hasDraft?: boolean;
  hadDraft?: boolean;
  step?: number;
  stepCount?: number;
  lastStep?: number;
  draftAgeSeconds?: number;
  error?: boolean;
  environment?: string;
  // Login-specific dimensions (bounded, non-PII)
  result?: "success" | "error";
  durationBucket?: string;
  errorCode?: string;
  action?: "retry" | "clear_session";
}

// ============================================================================
// Session Management (anonymous, no PII)
// ============================================================================

function getSessionId(): string {
  let sessionId = sessionStorage.getItem("exp_session_id");
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    sessionStorage.setItem("exp_session_id", sessionId);
  }
  return sessionId;
}

// ============================================================================
// Event Buffer (offline resilience)
// ============================================================================

function getEventBuffer(): TelemetryEvent[] {
  try {
    const buffer = localStorage.getItem(EVENT_BUFFER_KEY);
    return buffer ? JSON.parse(buffer) : [];
  } catch {
    return [];
  }
}

function addToBuffer(event: TelemetryEvent): void {
  try {
    const buffer = getEventBuffer();
    buffer.push(event);
    // Keep buffer bounded
    const trimmed = buffer.slice(-MAX_BUFFER_SIZE);
    localStorage.setItem(EVENT_BUFFER_KEY, JSON.stringify(trimmed));
  } catch {
    // Storage quota exceeded - silently fail
  }
}

function clearBuffer(): void {
  try {
    localStorage.removeItem(EVENT_BUFFER_KEY);
  } catch {
    // Ignore
  }
}

// ============================================================================
// Event Emission
// ============================================================================

/**
 * Send event to backend API.
 * SILENT: Never throws, never logs errors (ADR-0004).
 */
async function sendToBackend(event: TelemetryEvent): Promise<boolean> {
  // === QUARANTINE: Skip API calls when disabled (ADR-0004) ===
  if (!TELEMETRY_ENABLED) {
    silentLog("Telemetry disabled, skipping API call");
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/telemetry/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    return response.ok;
  } catch {
    // SILENT: No console.error - ADR-0004 requires no console spam
    return false;
  }
}

/**
 * Flush buffered events to backend.
 * SILENT: Never throws, never logs errors (ADR-0004).
 */
async function flushBuffer(): Promise<void> {
  // === QUARANTINE: Skip API calls when disabled (ADR-0004) ===
  if (!TELEMETRY_ENABLED) {
    silentLog("Telemetry disabled, skipping buffer flush");
    return;
  }

  const buffer = getEventBuffer();
  if (buffer.length === 0) return;

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/telemetry/events/batch`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: buffer }),
      },
    );

    if (response.ok) {
      clearBuffer();
    }
    // SILENT: No logging on failure - ADR-0004
  } catch {
    // SILENT: Keep buffer for retry, no console.error - ADR-0004
  }
}

/**
 * Track an experiment event.
 * NEVER blocks user workflows. NEVER spams console (ADR-0004).
 */
export function trackExpEvent(
  eventName: string,
  dimensions: ExpEventDimensions = {},
): void {
  const event: TelemetryEvent = {
    name: eventName,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    dimensions: {
      ...dimensions,
      environment: IS_PRODUCTION
        ? "production"
        : IS_STAGING
          ? "staging"
          : "development",
    },
  };

  // === SILENT LOGGING: Only in development, never staging/production (ADR-0004) ===
  silentLog(eventName, event.dimensions);

  // Add to buffer first (offline resilience)
  addToBuffer(event);

  // Try to send immediately (async, non-blocking)
  sendToBackend(event).then((sent) => {
    if (sent) {
      // Remove from buffer if sent successfully
      const buffer = getEventBuffer();
      const updated = buffer.filter((e) => e.timestamp !== event.timestamp);
      if (updated.length < buffer.length) {
        try {
          localStorage.setItem(EVENT_BUFFER_KEY, JSON.stringify(updated));
        } catch {
          // SILENT: Ignore storage errors - ADR-0004
        }
      }
    }
    // SILENT: No logging on failure - ADR-0004
  });
}

// ============================================================================
// EXP-001 Specific Events (Convenience Functions)
// ============================================================================

/**
 * Track form opened (session start)
 */
export function trackExp001FormOpened(
  formType: string,
  flagEnabled: boolean,
  hasDraft: boolean,
): void {
  trackExpEvent("exp001_form_opened", {
    formType,
    flagEnabled,
    hasDraft,
  });
}

/**
 * Track draft saved
 */
export function trackExp001DraftSaved(formType: string, step: number): void {
  trackExpEvent("exp001_draft_saved", {
    formType,
    step,
  });
}

/**
 * Track draft recovered
 */
export function trackExp001DraftRecovered(
  formType: string,
  draftAgeSeconds: number,
): void {
  trackExpEvent("exp001_draft_recovered", {
    formType,
    draftAgeSeconds,
  });
}

/**
 * Track draft discarded
 */
export function trackExp001DraftDiscarded(
  formType: string,
  draftAgeSeconds: number,
): void {
  trackExpEvent("exp001_draft_discarded", {
    formType,
    draftAgeSeconds,
  });
}

/**
 * Track form submitted (primary sample event)
 */
export function trackExp001FormSubmitted(
  formType: string,
  flagEnabled: boolean,
  hadDraft: boolean,
  stepCount: number,
  error: boolean = false,
): void {
  trackExpEvent("exp001_form_submitted", {
    formType,
    flagEnabled,
    hadDraft,
    stepCount,
    error,
  });
}

/**
 * Track form abandoned (session end without submit)
 */
export function trackExp001FormAbandoned(
  formType: string,
  flagEnabled: boolean,
  lastStep: number,
  hadDraft: boolean,
): void {
  trackExpEvent("exp001_form_abandoned", {
    formType,
    flagEnabled,
    lastStep,
    hadDraft,
  });
}

// ============================================================================
// Login Telemetry (LOGIN_UX_CONTRACT.md)
// ============================================================================

// Bounded types for login telemetry
export type LoginErrorCode =
  | "TIMEOUT"
  | "UNAUTHORIZED"
  | "UNAVAILABLE"
  | "SERVER_ERROR"
  | "NETWORK_ERROR"
  | "UNKNOWN";

export type DurationBucket =
  | "fast"
  | "normal"
  | "slow"
  | "very_slow"
  | "timeout";

interface LoginEventDimensions {
  result: "success" | "error";
  durationBucket: DurationBucket;
  errorCode?: LoginErrorCode;
}

/**
 * Track login attempt completion (bounded, non-PII)
 */
export function trackLoginCompleted(
  result: "success" | "error",
  durationBucket: DurationBucket,
  errorCode?: LoginErrorCode,
): void {
  const dimensions: LoginEventDimensions = {
    result,
    durationBucket,
    ...(errorCode && { errorCode }),
  };

  trackExpEvent("login_completed", dimensions);
}

/**
 * Track login error shown to user
 */
export function trackLoginErrorShown(errorCode: LoginErrorCode): void {
  trackExpEvent("login_error_shown", { errorCode });
}

/**
 * Track login recovery action taken
 */
export function trackLoginRecoveryAction(
  action: "retry" | "clear_session",
): void {
  trackExpEvent("login_recovery_action", { action });
}

/**
 * Track slow warning shown
 */
export function trackLoginSlowWarning(): void {
  trackExpEvent("login_slow_warning", {});
}

// ============================================================================
// Initialize
// ============================================================================

// Try to flush buffer on load
if (typeof window !== "undefined") {
  window.addEventListener("load", () => {
    setTimeout(flushBuffer, 5000); // Delay to avoid blocking initial load
  });

  // Also try on visibility change (user returns to tab)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      flushBuffer();
    }
  });
}

export default {
  trackExpEvent,
  trackExp001FormOpened,
  trackExp001DraftSaved,
  trackExp001DraftRecovered,
  trackExp001DraftDiscarded,
  trackExp001FormSubmitted,
  trackExp001FormAbandoned,
  flushBuffer,
};
