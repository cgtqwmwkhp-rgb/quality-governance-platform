/**
 * Telemetry Service for EXP-001 and future experiments
 * 
 * Emits events to:
 * 1. Backend API (for server-side aggregation)
 * 2. Console (for staging debugging)
 * 3. LocalStorage buffer (for offline resilience)
 * 
 * NO PII POLICY:
 * - All dimensions must be bounded (enums, not free text)
 * - No user IDs, emails, names, or identifiable data
 * - Form content is NOT captured, only metadata
 */

import { API_BASE_URL } from '../config/apiBase';

// Environment detection
const IS_PRODUCTION = window.location.hostname.includes('azurewebsites.net') && 
                      !window.location.hostname.includes('staging');
const IS_STAGING = window.location.hostname.includes('staging') || 
                   window.location.hostname === 'localhost';

// Event buffer for offline resilience
const EVENT_BUFFER_KEY = 'exp_telemetry_buffer';
const MAX_BUFFER_SIZE = 100;

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
}

// ============================================================================
// Session Management (anonymous, no PII)
// ============================================================================

function getSessionId(): string {
  let sessionId = sessionStorage.getItem('exp_session_id');
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    sessionStorage.setItem('exp_session_id', sessionId);
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
 * Send event to backend API
 */
async function sendToBackend(event: TelemetryEvent): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/telemetry/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Flush buffered events to backend
 */
async function flushBuffer(): Promise<void> {
  const buffer = getEventBuffer();
  if (buffer.length === 0) return;
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/telemetry/events/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events: buffer }),
    });
    
    if (response.ok) {
      clearBuffer();
    }
  } catch {
    // Keep buffer for retry
  }
}

/**
 * Track an experiment event
 */
export function trackExpEvent(
  eventName: string,
  dimensions: ExpEventDimensions = {}
): void {
  const event: TelemetryEvent = {
    name: eventName,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    dimensions: {
      ...dimensions,
      environment: IS_PRODUCTION ? 'production' : IS_STAGING ? 'staging' : 'development',
    },
  };
  
  // Console log in non-production (for debugging)
  if (!IS_PRODUCTION) {
    console.log(`[Telemetry] ${eventName}`, event.dimensions);
  }
  
  // Add to buffer first (offline resilience)
  addToBuffer(event);
  
  // Try to send immediately
  sendToBackend(event).then((sent) => {
    if (sent) {
      // Remove from buffer if sent successfully
      const buffer = getEventBuffer();
      const updated = buffer.filter((e) => e.timestamp !== event.timestamp);
      if (updated.length < buffer.length) {
        try {
          localStorage.setItem(EVENT_BUFFER_KEY, JSON.stringify(updated));
        } catch {
          // Ignore
        }
      }
    }
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
  hasDraft: boolean
): void {
  trackExpEvent('exp001_form_opened', {
    formType,
    flagEnabled,
    hasDraft,
  });
}

/**
 * Track draft saved
 */
export function trackExp001DraftSaved(
  formType: string,
  step: number
): void {
  trackExpEvent('exp001_draft_saved', {
    formType,
    step,
  });
}

/**
 * Track draft recovered
 */
export function trackExp001DraftRecovered(
  formType: string,
  draftAgeSeconds: number
): void {
  trackExpEvent('exp001_draft_recovered', {
    formType,
    draftAgeSeconds,
  });
}

/**
 * Track draft discarded
 */
export function trackExp001DraftDiscarded(
  formType: string,
  draftAgeSeconds: number
): void {
  trackExpEvent('exp001_draft_discarded', {
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
  error: boolean = false
): void {
  trackExpEvent('exp001_form_submitted', {
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
  hadDraft: boolean
): void {
  trackExpEvent('exp001_form_abandoned', {
    formType,
    flagEnabled,
    lastStep,
    hadDraft,
  });
}

// ============================================================================
// Initialize
// ============================================================================

// Try to flush buffer on load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    setTimeout(flushBuffer, 5000); // Delay to avoid blocking initial load
  });
  
  // Also try on visibility change (user returns to tab)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
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
