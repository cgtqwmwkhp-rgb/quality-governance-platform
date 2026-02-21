/**
 * useFormAutosave - Autosave form data to localStorage with draft recovery
 *
 * Part of EXP-001: Autosave + Draft Recovery for Portal Forms
 * Feature Flag: portal_form_autosave
 *
 * PII-SAFE: Does not store raw PII. Stores only form field values
 * with session-scoped keys.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  trackExp001DraftSaved,
  trackExp001DraftRecovered,
  trackExp001DraftDiscarded,
} from "../services/telemetry";

// Storage schema version for future migrations
const SCHEMA_VERSION = "1.0";

// Draft expiry time (24 hours in milliseconds)
const DRAFT_EXPIRY_MS = 24 * 60 * 60 * 1000;

// Debounce delay for saves (500ms)
const SAVE_DEBOUNCE_MS = 500;

// Storage key prefix
const STORAGE_KEY_PREFIX = "portal_form_draft_";

export interface FormDraft<T> {
  formType: string;
  data: T;
  step: number;
  savedAt: string;
  expiresAt: string;
  version: string;
}

export interface UseFormAutosaveOptions<T> {
  formType: string;
  enabled?: boolean;
  onDraftFound?: (draft: FormDraft<T>) => void;
}

export interface UseFormAutosaveReturn<T> {
  // State
  hasDraft: boolean;
  draftData: FormDraft<T> | null;
  isRecoveryPromptOpen: boolean;
  lastSavedAt: Date | null;

  // Actions
  saveNow: (data: T, step: number) => void;
  saveDraft: (data: T, step: number) => void;
  recoverDraft: () => T | null;
  discardDraft: () => void;
  clearDraft: () => void;

  // UI handlers
  openRecoveryPrompt: () => void;
  closeRecoveryPrompt: () => void;
}

/**
 * Check if localStorage is available
 */
function isLocalStorageAvailable(): boolean {
  try {
    const testKey = "__storage_test__";
    localStorage.setItem(testKey, testKey);
    localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get storage key for a form type
 */
function getStorageKey(formType: string): string {
  return `${STORAGE_KEY_PREFIX}${formType}`;
}

/**
 * Check if a draft is expired
 */
function isDraftExpired(draft: FormDraft<unknown>): boolean {
  try {
    const expiresAt = new Date(draft.expiresAt);
    return expiresAt <= new Date();
  } catch {
    return true;
  }
}

/**
 * useFormAutosave Hook
 *
 * Provides autosave functionality for forms with:
 * - Debounced saving to localStorage
 * - Draft recovery prompts
 * - Automatic expiry (24 hours)
 * - Graceful error handling
 */
export function useFormAutosave<T extends Record<string, unknown>>(
  options: UseFormAutosaveOptions<T>,
): UseFormAutosaveReturn<T> {
  const { formType, enabled = true, onDraftFound } = options;

  const [hasDraft, setHasDraft] = useState(false);
  const [draftData, setDraftData] = useState<FormDraft<T> | null>(null);
  const [isRecoveryPromptOpen, setIsRecoveryPromptOpen] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);

  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const storageAvailable = useRef(isLocalStorageAvailable());

  // Load existing draft on mount
  useEffect(() => {
    if (!enabled || !storageAvailable.current) return;

    try {
      const key = getStorageKey(formType);
      const stored = localStorage.getItem(key);

      if (stored) {
        const draft = JSON.parse(stored) as FormDraft<T>;

        // Check version compatibility
        if (draft.version !== SCHEMA_VERSION) {
          // Schema mismatch - discard old draft
          localStorage.removeItem(key);
          return;
        }

        // Check if expired
        if (isDraftExpired(draft)) {
          localStorage.removeItem(key);
          return;
        }

        // Valid draft found
        setHasDraft(true);
        setDraftData(draft);
        setIsRecoveryPromptOpen(true);

        if (onDraftFound) {
          onDraftFound(draft);
        }
      }
    } catch (error) {
      console.warn("[useFormAutosave] Failed to load draft:", error);
    }
  }, [formType, enabled, onDraftFound]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Save immediately (no debounce)
   */
  const saveNow = useCallback(
    (data: T, step: number) => {
      if (!enabled || !storageAvailable.current) return;

      try {
        const now = new Date();
        const draft: FormDraft<T> = {
          formType,
          data,
          step,
          savedAt: now.toISOString(),
          expiresAt: new Date(now.getTime() + DRAFT_EXPIRY_MS).toISOString(),
          version: SCHEMA_VERSION,
        };

        const key = getStorageKey(formType);
        localStorage.setItem(key, JSON.stringify(draft));
        setLastSavedAt(now);
        setHasDraft(true);
        setDraftData(draft);

        // Emit telemetry event (EXP-001)
        trackExp001DraftSaved(formType, step);
      } catch (error) {
        // Quota exceeded or other storage error - fail silently
        console.warn("[useFormAutosave] Failed to save draft:", error);
      }
    },
    [formType, enabled],
  );

  /**
   * Save with debounce
   */
  const saveDraft = useCallback(
    (data: T, step: number) => {
      if (!enabled || !storageAvailable.current) return;

      // Clear existing timeout
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }

      // Schedule new save
      saveTimeoutRef.current = setTimeout(() => {
        saveNow(data, step);
      }, SAVE_DEBOUNCE_MS);
    },
    [enabled, saveNow],
  );

  /**
   * Recover draft data
   */
  const recoverDraft = useCallback((): T | null => {
    if (draftData) {
      setIsRecoveryPromptOpen(false);

      // Calculate draft age for telemetry (EXP-001)
      const draftAgeSeconds = Math.round(
        (Date.now() - new Date(draftData.savedAt).getTime()) / 1000,
      );
      trackExp001DraftRecovered(formType, draftAgeSeconds);

      return draftData.data;
    }
    return null;
  }, [draftData, formType]);

  /**
   * Discard draft (user chose not to recover)
   */
  const discardDraft = useCallback(() => {
    if (!storageAvailable.current) return;

    try {
      // Calculate draft age for telemetry (EXP-001)
      if (draftData) {
        const draftAgeSeconds = Math.round(
          (Date.now() - new Date(draftData.savedAt).getTime()) / 1000,
        );
        trackExp001DraftDiscarded(formType, draftAgeSeconds);
      }

      const key = getStorageKey(formType);
      localStorage.removeItem(key);
      setHasDraft(false);
      setDraftData(null);
      setIsRecoveryPromptOpen(false);
      setLastSavedAt(null);
    } catch (error) {
      console.warn("[useFormAutosave] Failed to discard draft:", error);
    }
  }, [formType, draftData]);

  /**
   * Clear draft (after successful submission)
   */
  const clearDraft = useCallback(() => {
    discardDraft();
  }, [discardDraft]);

  /**
   * UI handlers
   */
  const openRecoveryPrompt = useCallback(() => {
    if (hasDraft) {
      setIsRecoveryPromptOpen(true);
    }
  }, [hasDraft]);

  const closeRecoveryPrompt = useCallback(() => {
    setIsRecoveryPromptOpen(false);
  }, []);

  return {
    hasDraft,
    draftData,
    isRecoveryPromptOpen,
    lastSavedAt,
    saveNow,
    saveDraft,
    recoverDraft,
    discardDraft,
    clearDraft,
    openRecoveryPrompt,
    closeRecoveryPrompt,
  };
}

export default useFormAutosave;
