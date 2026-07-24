import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import {
  getPlatformToken,
  getPlatformRefreshToken,
  isTokenExpired,
  clearAuthState,
  establishPlatformSession,
} from '../utils/auth'
import { API_BASE_URL } from '../config/apiBase'
import { toast } from '../contexts/ToastContext'
import { useAppStore } from '../stores/useAppStore'
import { flushAllDraftsToIndexedDb } from '../services/auditDraftStore'
import { createRiskRegisterApi } from './riskRegisterClient'
import { createNotificationsApi } from './notificationsClient'
import { createInvestigationsApi } from './investigationsClient'
import { createActionsApi } from './actionsClient'
import { createIncidentsApi } from './incidentsClient'
import { createPoliciesApi } from './policiesClient'
import { createRtasApi } from './rtasClient'
import { createHsKpisApi } from './hsKpisClient'
import { createSafetyInsightsApi } from './safetyInsightsClient'
import { createComplaintsApi } from './complaintsClient'
import { createNearMissesApi } from './nearMissesClient'
import { createRisksApi } from './risksClient'
import { createStandardsApi } from './standardsClient'
import { createAuditsApi } from './auditsClient'
import { createWorkforceApi } from './workforceClient'
import { createEngineersApi } from './engineersClient'
import { createPlanetMarkApi } from './planetMarkClient'
import { createUvdbApi } from './uvdbClient'
import { createUsersApi } from './usersClient'
import { createWorkflowsApi } from './workflowsClient'
import type { AssuranceCertShelfResponse } from './assuranceCertShelfTypes'
import { createAuditTrailApi } from './auditTrailClient'
import { createSignaturesApi } from './signaturesClient'
import { createLookupsApi } from './lookupsClient'
import { createKnowledgeBankApi } from './knowledgeBankClient'
import { createDocumentControlApi } from './documentControlClient'
import { createDocumentCampaignApi } from './documentCampaignClient'
import { createTrainingMatrixApi } from './trainingMatrixClient'
import { createPortalComplianceApi } from './portalComplianceClient'
import {
  beginGlobalLoading,
  endGlobalLoading,
  shouldTrackGlobalLoading,
} from './globalLoading'


// Opt-in global loading flag (see globalLoading.ts). Default: no global flash.
declare module 'axios' {
  export interface AxiosRequestConfig {
    globalLoading?: boolean
    /** When true, the response interceptor will not emit a global error toast (page handles inline). */
    suppressErrorToast?: boolean
  }
}

const ERROR_TOAST_DEDUPE_MS = 5000
let lastErrorToastMessage = ''
let lastErrorToastAt = 0

function maybeShowErrorToast(message: string, config?: InternalAxiosRequestConfig): void {
  if (config?.suppressErrorToast) {
    return
  }
  const now = Date.now()
  if (message === lastErrorToastMessage && now - lastErrorToastAt < ERROR_TOAST_DEDUPE_MS) {
    return
  }
  lastErrorToastMessage = message
  lastErrorToastAt = now
  toast.error(message)
}

// Use centralized API base URL from config (environment-aware)
const HTTPS_API_BASE = API_BASE_URL

// Adaptive request timeouts (PX-029 / ACT-052 Wave A1).
// 15s caused false timeouts on cold starts, large list reads, and write paths that
// wait on DB + side effects — which then falsely drove OfflineIndicator via
// connectionStatus. Reads get 30s; mutating verbs get 45s. Callers may still
// override (uploads / long-running process jobs).
const READ_TIMEOUT_MS = 30000
const WRITE_TIMEOUT_MS = 45000
/** @deprecated Prefer READ_TIMEOUT_MS / WRITE_TIMEOUT_MS — kept for refresh + callers. */
const REQUEST_TIMEOUT_MS = READ_TIMEOUT_MS

// Extended timeout for file uploads (2 minutes)
// File uploads to Azure Blob Storage can take longer, especially for large files
const UPLOAD_TIMEOUT_MS = 120000

// Extended timeout for import processing (5 minutes)
// PDF extraction + OCR + dual AI analysis (Mistral + Gemini) runs synchronously
const PROCESSING_TIMEOUT_MS = 300000

const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete'])

/**
 * Resolve per-request timeout. Preserves explicit caller overrides (e.g. uploads).
 */
export function resolveRequestTimeout(
  method?: string,
  currentTimeout?: number,
): number {
  if (
    currentTimeout !== undefined &&
    currentTimeout !== READ_TIMEOUT_MS &&
    currentTimeout !== WRITE_TIMEOUT_MS
  ) {
    return currentTimeout
  }
  const m = (method ?? 'get').toLowerCase()
  return WRITE_METHODS.has(m) ? WRITE_TIMEOUT_MS : READ_TIMEOUT_MS
}

// ============ Bounded Error Codes (LOGIN_UX_CONTRACT.md) ============
// These are the ONLY allowed error codes for login
export type LoginErrorCode =
  | 'TIMEOUT'
  | 'UNAUTHORIZED'
  | 'UNAVAILABLE'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'UNKNOWN'

// i18n keys for Login error copy (bounded codes, no PII). English fallbacks below.
export const LOGIN_ERROR_I18N_KEYS: Record<LoginErrorCode, string> = {
  TIMEOUT: 'login.error.TIMEOUT',
  UNAUTHORIZED: 'login.error.UNAUTHORIZED',
  UNAVAILABLE: 'login.error.UNAVAILABLE',
  SERVER_ERROR: 'login.error.SERVER_ERROR',
  NETWORK_ERROR: 'login.error.NETWORK_ERROR',
  UNKNOWN: 'login.error.UNKNOWN',
}

/** @deprecated Prefer t(LOGIN_ERROR_I18N_KEYS[code]) — English fallbacks for non-i18n callers/tests */
export const LOGIN_ERROR_MESSAGES: Record<LoginErrorCode, string> = {
  TIMEOUT: 'Request timed out. Please try again.',
  UNAUTHORIZED: 'Incorrect email or password.',
  UNAVAILABLE: 'Service temporarily unavailable. Please try again in a few minutes.',
  SERVER_ERROR: 'Something went wrong. Please try again.',
  NETWORK_ERROR: 'Unable to connect. Please check your internet connection.',
  UNKNOWN: 'An unexpected error occurred. Please try again.',
}

// Duration buckets for telemetry
export type DurationBucket = 'fast' | 'normal' | 'slow' | 'very_slow' | 'timeout'

export function getDurationBucket(durationMs: number): DurationBucket {
  if (durationMs < 1000) return 'fast'
  if (durationMs < 3000) return 'normal'
  if (durationMs < 7000) return 'slow'
  if (durationMs < 15000) return 'very_slow'
  return 'timeout'
}

/**
 * Classify an error into a bounded LoginErrorCode.
 * MUST return one of the defined codes - no exceptions.
 */
export function classifyLoginError(error: unknown): LoginErrorCode {
  if (!axios.isAxiosError(error)) {
    return 'UNKNOWN'
  }

  const axiosError = error as AxiosError

  // Timeout check first (no response)
  if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
    return 'TIMEOUT'
  }

  // Network error (no response received)
  if (!axiosError.response) {
    return 'NETWORK_ERROR'
  }

  // HTTP status-based classification
  const status = axiosError.response.status

  if (status === 401) {
    return 'UNAUTHORIZED'
  }

  if (status === 502 || status === 503) {
    return 'UNAVAILABLE'
  }

  if (status >= 500) {
    return 'SERVER_ERROR'
  }

  // Any other error
  return 'UNKNOWN'
}

// ============ Bounded Error Classes for API Responses ============
// Universal error classification for all API calls

export enum ErrorClass {
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  AUTH_ERROR = 'AUTH_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  WRITE_BLOCKED = 'WRITE_BLOCKED',
  NETWORK_ERROR = 'NETWORK_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  SETUP_REQUIRED = 'SETUP_REQUIRED',
  UNKNOWN = 'UNKNOWN',
}

// Re-export SetupRequired types for convenience
export { isSetupRequired, SetupRequiredPanel } from '../components/ui/SetupRequiredPanel'
export type { SetupRequiredResponse } from '../components/ui/SetupRequiredPanel'

export interface ApiError extends Error {
  error_class: ErrorClass
  status_code?: number
  detail?: string
}

/**
 * Classify any error into a bounded ErrorClass.
 * Used for deterministic UX states.
 */
export function classifyError(error: unknown): ErrorClass {
  if (!axios.isAxiosError(error)) {
    return ErrorClass.UNKNOWN
  }

  const axiosError = error as AxiosError

  // Network error (no response)
  if (!axiosError.response) {
    if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
      return ErrorClass.NETWORK_ERROR
    }
    return ErrorClass.NETWORK_ERROR
  }

  const status = axiosError.response.status

  if (status === 400 || status === 422) {
    return ErrorClass.VALIDATION_ERROR
  }
  if (status === 401 || status === 403) {
    return ErrorClass.AUTH_ERROR
  }
  if (status === 404) {
    return ErrorClass.NOT_FOUND
  }
  if (status === 409) {
    const data = axiosError.response.data as Record<string, unknown> | undefined
    if (data?.error_class === 'UAT_WRITE_BLOCKED') {
      return ErrorClass.WRITE_BLOCKED
    }
  }
  if (status >= 500) {
    return ErrorClass.SERVER_ERROR
  }

  return ErrorClass.UNKNOWN
}

/**
 * Create a typed ApiError from any caught error.
 */
export function createApiError(error: unknown): ApiError {
  const errorClass = classifyError(error)
  const apiError = new Error('API Error') as ApiError
  apiError.error_class = errorClass

  if (axios.isAxiosError(error) && error.response) {
    apiError.status_code = error.response.status
    apiError.detail = error.response.data?.detail || error.response.data?.message || error.message
  }

  return apiError
}

const api = axios.create({
  baseURL: HTTPS_API_BASE,
  timeout: READ_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
})

const ACTIONS_OR_CAPA_PATH = /(?:^|\/)(?:actions|capa)(?:\/|$)/
const IDEMPOTENT_WRITE_METHODS = new Set(['post', 'put', 'patch'])

/** Non-create POST verbs (RPC / auth / analysis) — do not auto-attach Idempotency-Key. */
const NON_CREATE_POST_PATH =
  /\/(?:auth\/(?:login|logout|refresh|token-exchange)|[^/?]*\/(?:publish|queue|process|promote|bulk-review|analyze(?:-[^/?]+)?|search|forecast|review|check|prepare|submit|acknowledge|open|sync|link-investigation|approve|reject|bulk-approve|auto-tag|run|generate-[^/?]+))(?:\/|$|\?)/i

export function newIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return `qgp-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/** True only for action/CAPA writes handled by the server idempotency middleware. */
export function needsActionWriteIdempotency(url?: string, method?: string): boolean {
  if (!url || !method || !IDEMPOTENT_WRITE_METHODS.has(method.toLowerCase())) return false
  return ACTIONS_OR_CAPA_PATH.test(url.split('?')[0])
}

/**
 * True for create-style POSTs (resource collection creates).
 * Backend IdempotencyMiddleware only activates when the header is present.
 */
export function needsCreatePostIdempotency(url?: string, method?: string): boolean {
  if (!url || !method || method.toLowerCase() !== 'post') return false
  const path = url.split('?')[0]
  if (isAuthEndpoint(path)) return false
  if (NON_CREATE_POST_PATH.test(path)) return false
  return path.includes('/api/')
}

export function needsWriteIdempotency(url?: string, method?: string): boolean {
  return needsActionWriteIdempotency(url, method) || needsCreatePostIdempotency(url, method)
}

function ensureIdempotencyKey(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const headers = config.headers as Record<string, string | undefined>
  if (!headers['Idempotency-Key'] && !headers['idempotency-key']) {
    headers['Idempotency-Key'] = newIdempotencyKey()
  }
  return config
}

/**
 * Add a per-request key while preserving a caller-supplied key.
 *
 * Axios preserves this header when a 401 triggers its single retry, so the
 * retry remains a duplicate of the original write rather than a new mutation.
 */
export function applyActionWriteIdempotency(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  if (!needsActionWriteIdempotency(config.url, config.method)) return config
  return ensureIdempotencyKey(config)
}

/**
 * Attach Idempotency-Key to create POSTs (and action/CAPA writes).
 * Prefer this over blind retry after a timeout — see maybeCommitted below.
 */
export function applyCreatePostIdempotency(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  if (!needsWriteIdempotency(config.url, config.method)) return config
  return ensureIdempotencyKey(config)
}

/** In-flight count for requests that opted into globalLoading. */
let activeGlobalLoadingRequests = 0

// Token refresh: prevent infinite loops and queue concurrent 401s
let refreshPromise: Promise<string | null> | null = null

function isAuthEndpoint(url?: string): boolean {
  if (!url) return false
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/token-exchange') ||
    url.includes('/auth/refresh')
  )
}

function isPortalPath(pathname: string): boolean {
  return pathname === '/portal' || pathname.startsWith('/portal/')
}

function isLoginPagePath(pathname: string): boolean {
  // Only true login routes — /portal itself is an authenticated shell.
  return pathname === '/login' || pathname === '/portal/login'
}

function getLoginRedirectPath(pathname: string): string {
  return isPortalPath(pathname) ? '/portal/login' : '/login'
}

function isLocalDevHost(url: string): boolean {
  return url.includes('localhost') || url.includes('127.0.0.1')
}

/**
 * Centralised auth-loss handler. Stashes any in-flight audit drafts to
 * IndexedDB BEFORE clearing tokens so the user can recover their unsaved
 * answers after re-login. The flush is fire-and-forget — we never block
 * navigation on it (browsers throttle JS once `location.href` is set, but
 * IndexedDB writes through `idb` are typically <50ms and the OS will let
 * them complete).
 *
 * Always call this instead of the bare clearTokens() + window.location.href
 * pattern so soft-recovery is consistent everywhere.
 */
function clearAndRedirectToLogin(): void {
  try {
    void flushAllDraftsToIndexedDb('auth-loss')
  } catch {
    /* never let the soft-recovery hook block the redirect */
  }
  clearAuthState()
  const currentPath = window.location.pathname
  const isLoginPage = isLoginPagePath(currentPath)
  if (!isLoginPage) {
    window.location.href = getLoginRedirectPath(currentPath)
  }
}

async function doRefreshToken(): Promise<string | null> {
  const refreshToken = getPlatformRefreshToken()
  if (!refreshToken) {
    return null
  }
  try {
    const res = await axios.post<RefreshResponse>(
      `${HTTPS_API_BASE}/api/v1/auth/refresh`,
      { refresh_token: refreshToken },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: REQUEST_TIMEOUT_MS,
      },
    )
    const data = res.data
    if (data.access_token) {
      // Keep admin + portal stores in lockstep after refresh.
      establishPlatformSession(data.access_token, data.refresh_token)
      return data.access_token
    }
    return null
  } catch {
    return null
  }
}

async function refreshAndGetToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise
  }
  refreshPromise = doRefreshToken()
  try {
    const token = await refreshPromise
    return token
  } finally {
    refreshPromise = null
  }
}

/**
 * Public wrapper around the single-flight refresh helper.
 *
 * Safe to call from anywhere (e.g. a session-keepalive hook). Returns the
 * new access token on success, or null if refresh isn't possible (no refresh
 * token on disk, or the server rejected the refresh request).
 *
 * Concurrent callers share the same in-flight refresh promise, so we never
 * issue more than one /auth/refresh request at a time.
 */
export async function refreshSession(): Promise<string | null> {
  return refreshAndGetToken()
}

// CRITICAL: Enforce HTTPS on all requests at interceptor level
api.interceptors.request.use(async (config) => {
  const trackGlobalLoading = shouldTrackGlobalLoading(config)
  activeGlobalLoadingRequests = beginGlobalLoading(
    activeGlobalLoadingRequests,
    trackGlobalLoading,
    (loading) => useAppStore.getState().setLoading(loading),
  )
  config.timeout = resolveRequestTimeout(config.method, config.timeout)
  // Create POSTs + Actions/CAPA writes — stable key survives auth-refresh retry.
  applyCreatePostIdempotency(config)
  // Force HTTPS on baseURL
  if (config.baseURL && !isLocalDevHost(config.baseURL) && !config.baseURL.startsWith('https://')) {
    config.baseURL = config.baseURL.replace(/^http:/, 'https:')
    if (!config.baseURL.startsWith('https://')) {
      config.baseURL = 'https://' + config.baseURL.replace(/^\/\//, '')
    }
  }

  // Force HTTPS on URL if it's absolute
  if (config.url && config.url.startsWith('http:') && !isLocalDevHost(config.url)) {
    config.url = config.url.replace(/^http:/, 'https:')
  }

  // Add auth token using centralized accessor
  let token = getPlatformToken()

  // DEBUG: Log auth header presence (not the token itself)
  const isApiCall = config.url?.startsWith('/api/')
  const isAuthEndpointUrl =
    config.url?.includes('/auth/login') ||
    config.url?.includes('/auth/token-exchange') ||
    config.url?.includes('/auth/refresh')

  if (import.meta.env.DEV && isApiCall && !isAuthEndpointUrl) {
    console.log(
      `[Auth Debug] ${config.method?.toUpperCase()} ${config.url} | token_present=${!!token} | token_length=${token?.length || 0}`,
    )
  }

  // FormData must set its own multipart boundary — never force application/json
  // or a bare multipart/form-data header (breaks Library + evidence uploads).
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && typeof config.headers === 'object') {
      if (typeof (config.headers as { delete?: (k: string) => void }).delete === 'function') {
        ;(config.headers as { delete: (k: string) => void }).delete('Content-Type')
      } else {
        delete (config.headers as Record<string, unknown>)['Content-Type']
        delete (config.headers as Record<string, unknown>)['content-type']
      }
    }
  }

  if (token && !isAuthEndpointUrl) {
    // If the access token is expired (or about to expire), try to silently
    // refresh BEFORE clearing anything. The previous behaviour was to call
    // clearTokens() here, which removed the refresh token too and forced a
    // hard redirect to /login — making long audit sessions on tablets
    // (where >30 min can pass between API calls) look like an unexpected
    // logout. Now we attempt refresh first; only if that fails do we clear.
    if (isTokenExpired(token)) {
      const refreshToken = getPlatformRefreshToken()
      if (refreshToken) {
        if (import.meta.env.DEV)
          console.warn('[Axios] Access token expired - attempting silent refresh')
        try {
          const newToken = await refreshAndGetToken()
          if (newToken) {
            token = newToken
          } else {
            token = null
          }
        } catch {
          token = null
        }
      } else {
        token = null
      }

      if (!token) {
        if (import.meta.env.DEV)
          console.warn('[Axios] Token expired and refresh failed - redirecting to login')
        clearAndRedirectToLogin()
        activeGlobalLoadingRequests = endGlobalLoading(
          activeGlobalLoadingRequests,
          trackGlobalLoading,
          (loading) => useAppStore.getState().setLoading(loading),
        )
        return Promise.reject(new Error('Token expired - redirecting to login'))
      }
    }

    config.headers.Authorization = `Bearer ${token}`
  } else if (import.meta.env.DEV && isApiCall && !isAuthEndpointUrl) {
    console.warn('[Auth Debug] No token available for API call - will likely get 401')
  }
  return config
})

interface ClassifiedAxiosError extends AxiosError {
  classifiedMessage?: string
  isTimeout?: boolean
  /** POST/PUT/PATCH timed out — server may have committed; do not blind-retry. */
  maybeCommitted?: boolean
}

/** Timeout / AbortController cancel (axios ECONNABORTED / CanceledError). */
export function isTimeoutOrAbortError(error: {
  code?: string
  message?: string
  name?: string
}): boolean {
  if (error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED') return true
  if (error.name === 'CanceledError' || error.name === 'AbortError') return true
  return typeof error.message === 'string' && error.message.toLowerCase().includes('timeout')
}

/**
 * Whether a transport failure should drive OfflineIndicator via connectionStatus.
 * PX-029: timeout/abort while navigator.onLine must NOT mark the app Offline.
 */
export function shouldMarkConnectionDisconnected(error: {
  code?: string
  message?: string
  name?: string
  response?: unknown
}): boolean {
  if (error.response) return false
  const browserOnline =
    typeof navigator === 'undefined' ? true : navigator.onLine !== false
  if (isTimeoutOrAbortError(error) && browserOnline) {
    return false
  }
  return true
}

/**
 * Classify write-timeout disposition for UX. POST (and other mutations) that
 * time out are maybe-committed — reconcile/list before retrying; Idempotency-Key
 * makes a deliberate retry safe, but blind retry is discouraged.
 */
export function classifyWriteTimeoutDisposition(
  error: { code?: string; message?: string; name?: string },
  method?: string,
): 'maybe_committed' | 'safe_retry_read' | 'not_timeout' {
  if (!isTimeoutOrAbortError(error)) return 'not_timeout'
  const m = (method ?? 'get').toLowerCase()
  if (WRITE_METHODS.has(m) && m !== 'delete') {
    // DELETE is usually idempotent; POST/PUT/PATCH creates/updates may have landed.
    return 'maybe_committed'
  }
  if (m === 'delete') return 'maybe_committed'
  return 'safe_retry_read'
}

export function isMaybeCommittedTimeout(
  error: { code?: string; message?: string; name?: string; config?: { method?: string } },
): boolean {
  return classifyWriteTimeoutDisposition(error, error.config?.method) === 'maybe_committed'
}

api.interceptors.response.use(
  (response) => {
    activeGlobalLoadingRequests = endGlobalLoading(
      activeGlobalLoadingRequests,
      shouldTrackGlobalLoading(response.config),
      (loading) => useAppStore.getState().setLoading(loading),
    )
    useAppStore.getState().setConnectionStatus('connected')
    return response
  },
  async (error: AxiosError) => {
    activeGlobalLoadingRequests = endGlobalLoading(
      activeGlobalLoadingRequests,
      shouldTrackGlobalLoading(error.config),
      (loading) => useAppStore.getState().setLoading(loading),
    )
    if (!error.response && shouldMarkConnectionDisconnected(error)) {
      useAppStore.getState().setConnectionStatus('disconnected')
    }
    // Classify the error for better user messaging
    const status = error.response?.status
    const currentPath = window.location.pathname
    const isLoginPage = isLoginPagePath(currentPath)

    if (status === 401) {
      const requestUrl = error.config?.url ?? ''
      const isAuth = isAuthEndpoint(requestUrl)

      // Auth endpoints (login, token-exchange, refresh): never try refresh; clear and redirect
      if (isAuth && !isLoginPage) {
        clearAndRedirectToLogin()
        return Promise.reject(error)
      }

      // Data endpoint 401: attempt token refresh (refresh uses axios directly, so its 401 never reaches here)
      if (
        !isAuth &&
        error.config &&
        !(error.config as InternalAxiosRequestConfig & { _retry?: boolean })._retry
      ) {
        const config = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
        const refreshToken = getPlatformRefreshToken()
        if (!refreshToken) {
          clearAndRedirectToLogin()
          ;(error as ClassifiedAxiosError).classifiedMessage =
            'Session expired. Please sign in again.'
          return Promise.reject(error)
        }

        try {
          const newToken = await refreshAndGetToken()
          if (newToken) {
            config._retry = true
            config.headers.Authorization = `Bearer ${newToken}`
            return api.request(config)
          }
        } catch {
          // refreshAndGetToken returns null on failure; fall through to clear
        }

        clearAndRedirectToLogin()
      }

      ;(error as ClassifiedAxiosError).classifiedMessage = 'Session expired. Please sign in again.'
    } else if (status === 403) {
      ;(error as ClassifiedAxiosError).classifiedMessage =
        "You don't have permission to perform this action."
    } else if (status === 409) {
      const data409 = error.response?.data as Record<string, unknown> | undefined
      if (data409?.error_class === 'UAT_WRITE_BLOCKED') {
        ;(error as ClassifiedAxiosError).classifiedMessage =
          'This environment is in read-only mode. Contact your administrator to enable writes.'
      }
    } else if (status === 429) {
      const retryAfter = error.response?.headers?.['retry-after']
      const waitSec = retryAfter ? parseInt(retryAfter, 10) : undefined
      ;(error as ClassifiedAxiosError).classifiedMessage = waitSec
        ? `Too many requests. Please wait ${waitSec} seconds and try again.`
        : 'Too many requests. Please slow down and try again.'
    } else if (status === 422) {
      const data = error.response?.data as Record<string, unknown> | undefined
      const errorEnvelope = data?.['error'] as Record<string, unknown> | undefined
      const fieldErrors = (errorEnvelope?.['details'] as Record<string, unknown>)?.['errors'] as
        | Array<Record<string, string>>
        | undefined
      let validationMsg: string | undefined
      if (fieldErrors && Array.isArray(fieldErrors) && fieldErrors.length > 0) {
        validationMsg = fieldErrors.map((e) => `${e.field || 'field'}: ${e.message}`).join('; ')
      }
      ;(error as ClassifiedAxiosError).classifiedMessage =
        validationMsg ||
        (errorEnvelope?.['message'] as string) ||
        (data?.['detail'] as string) ||
        (data?.['message'] as string) ||
        'Validation error. Please check your input.'
    } else if (status && status >= 500) {
      const data500 = error.response?.data as Record<string, unknown> | undefined
      const errorEnvelope = data500?.['error'] as Record<string, unknown> | undefined
      const serverMsg =
        (errorEnvelope?.['message'] as string | undefined) ||
        (data500?.['detail'] as string | undefined)
      ;(error as ClassifiedAxiosError).classifiedMessage = serverMsg
        ? `Server error: ${serverMsg}`
        : 'Server error. Please try again later.'
    } else if (isTimeoutOrAbortError(error)) {
      const method = error.config?.method
      const maybeCommitted =
        classifyWriteTimeoutDisposition(error, method) === 'maybe_committed'
      ;(error as ClassifiedAxiosError).isTimeout = true
      ;(error as ClassifiedAxiosError).maybeCommitted = maybeCommitted
      ;(error as ClassifiedAxiosError).classifiedMessage = maybeCommitted
        ? 'Request timed out. Your changes may already have been saved — refresh or check the list before trying again.'
        : 'Request timed out. Please try again.'
    } else if (!error.response) {
      ;(error as ClassifiedAxiosError).classifiedMessage =
        'Network error. Please check your connection and try again.'
    }

    const msg = (error as ClassifiedAxiosError).classifiedMessage
    if (msg && status !== 401) {
      maybeShowErrorToast(msg, error.config)
    }

    return Promise.reject(error)
  },
)

/**
 * Get a user-friendly error message from an API error.
 * Use this in catch blocks for consistent error messaging.
 */
export function getApiErrorMessage(error: unknown, fallback?: string): string {
  if (axios.isAxiosError(error)) {
    const classified = error as ClassifiedAxiosError
    if (classified.classifiedMessage) {
      return classified.classifiedMessage
    }
    const data = error.response?.data as Record<string, unknown> | undefined
    // Unified API envelope: {"error":{"code":"...","message":"..."}}
    const nestedError = data?.['error']
    if (nestedError && typeof nestedError === 'object' && nestedError !== null) {
      const nestedMessage = (nestedError as Record<string, unknown>)['message']
      if (typeof nestedMessage === 'string' && nestedMessage.trim()) {
        return nestedMessage
      }
    }
    if (typeof data?.['message'] === 'string' && data['message'].trim()) {
      return data['message'] as string
    }
    if (data?.['detail']) {
      if (typeof data['detail'] === 'string') {
        return data['detail']
      }
      if (
        typeof data['detail'] === 'object' &&
        data['detail'] !== null &&
        'message' in data['detail'] &&
        typeof (data['detail'] as Record<string, unknown>).message === 'string'
      ) {
        return (data['detail'] as Record<string, string>).message
      }
      return JSON.stringify(data['detail'])
    }
    // Prefer status-aware copy over raw Axios "Request failed with status code NNN"
    const status = error.response?.status
    if (status === 404) {
      return fallback ?? 'The requested record was not found.'
    }
    if (status === 401) {
      return fallback ?? 'Please sign in again to continue.'
    }
    if (status === 403) {
      return fallback ?? 'You do not have permission to perform this action.'
    }
    if (status && status >= 500) {
      return fallback ?? 'A server error occurred. Please try again.'
    }
    // Last resort - use axios error message
    return error.message
  }
  // Non-axios error
  if (error instanceof Error) {
    return error.message
  }
  return fallback ?? 'An unexpected error occurred'
}

// ============ Auth Types ============
export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  refresh_token?: string
}

export interface RefreshResponse {
  access_token: string
  refresh_token?: string
  token_type?: string
}

// ============ Common Types ============
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ============ Incident Types (extracted: incidentsClient.ts) ============
export type {
  Incident,
  IncidentCreate,
  IncidentUpdate,
  RunningSheetEntry,
} from './incidentsClient'

// ============ Near Miss Types (extracted: nearMissesClient.ts) ============
export type {
  NearMiss,
  NearMissCreate,
  NearMissUpdate,
} from './nearMissesClient'

// ============ RTA Types (extracted: rtasClient.ts) ============
export type {
  ThirdParty,
  Witness,
  RTA,
  RTACreate,
  RTAUpdate,
} from './rtasClient'

// ============ Complaint Types (extracted: complaintsClient.ts) ============
export type {
  Complaint,
  ComplaintCreate,
  ComplaintUpdate,
} from './complaintsClient'

// ============ Policy Types (extracted: policiesClient.ts) ============
export type {
  Policy,
  PolicyCreate,
} from './policiesClient'

// ============ Risk Types (extracted: risksClient.ts) ============
export type {
  Risk,
  RiskCreate,
} from './risksClient'

// ============ Audit Types (extracted: auditsClient.ts) ============
export type {
  ExternalAuditType,
  AuditRun,
  AuditFinding,
  AuditTemplate,
  CategoryCount,
  BatchImportResult,
  AuditTemplateCreate,
  AuditTemplateUpdate,
  AuditRunDetail,
  AuditRunCreate,
  AuditRunUpdate,
  AuditTemplateDetail,
  AuditSectionCreate,
  AuditSectionUpdate,
  SectionApplicabilityRules,
  QuestionOptionBase,
  EvidenceRequirement,
  ConditionalLogicRule,
  QuestionCriticality,
  AuditQuestionCreate,
  AuditQuestionUpdate,
  AuditSection,
  AuditQuestion,
  AuditResponse,
  AuditResponseCreate,
  AuditResponseUpdate,
  ResponseApplicability,
  AuditFindingCreate,
  AuditFindingUpdate,
  AuditAnalyticsSummary,
  AuditAnalyticsGroupBy,
  AuditAnalyticsDimensionItem,
  AuditAnalyticsDimensionsResponse,
  CriticalQueueItem,
  CriticalQueueResponse,
} from './auditsClient'

// ============ Workforce Development Types (extracted: workforceClient.ts) ============
export type {
  AssetType,
  Asset,
  AssessmentRun,
  InductionRun,
  EngineerProfile,
  CompetencyRecord,
  AssessmentResponseCreate,
  AssessmentResponseUpdate,
  InductionResponseCreate,
  InductionResponseUpdate,
  AssessmentResponseRecord,
  InductionResponseRecord,
  TrainingTicket,
  TrainingTicketCreate,
  TrainingTicketUpdate,
  TrainingTicketListResponse,
  TicketVerifyState,
  CompetencyRequirement,
  CompetencyRequirementCreate,
  CompetencyRequirementUpdate,
  CompetencyRequirementListResponse,
  CompetencyRequirementAllocateRequest,
  CompetencyRequirementAllocateResponse,
  WdpSummary,
  WdpEngineerMatrix,
  WdpTrends,
} from './workforceClient'

// ============ Standard Types ============
// ============ Standards Types (extracted: standardsClient.ts) ============
export type {
  Standard,
  Clause,
  ControlListItem,
  ComplianceScore,
} from './standardsClient'

export interface Control {
  id: number
  clause_id: number
  control_number: string
  title: string
  description?: string
  implementation_status?: string
  is_applicable: boolean
}

// ============ Action Types (extracted: actionsClient.ts) ============
export type {
  Action,
  ActionsSummary,
  ActionsViewCounts,
  ActionCreate,
  ActionUpdate,
  ActionOwnerNote,
  ActionOwnerNoteListResponse,
} from './actionsClient'

// ============ API Functions ============
export const authApi = {
  login: (data: LoginRequest) => api.post<LoginResponse>('/api/v1/auth/login', data),
  logout: (refreshToken?: string | null) =>
    api.post('/api/v1/auth/logout', refreshToken ? { refresh_token: refreshToken } : {}),
}

// NOTE: FastAPI has redirect_slashes=False. Trailing slashes MUST match
// the backend route definition exactly: routes with "/" need a trailing
// slash; routes like "/templates" must NOT have one.

// ============ Incidents API (extracted: incidentsClient.ts) ============
export const incidentsApi = createIncidentsApi(api)

// ============ RTAs API (extracted: rtasClient.ts) ============
export const rtasApi = createRtasApi(api)
export const hsKpisApi = createHsKpisApi(api)
export const safetyInsightsApi = createSafetyInsightsApi(api)
export type {
  DeepRunCreatePayload,
  SafetyInsightCaseRef,
  SafetyInsightDimension,
  SafetyInsightRun,
  SafetyInsightTheme,
} from './safetyInsightsClient'

// ============ Complaints API (extracted: complaintsClient.ts) ============
export const complaintsApi = createComplaintsApi(api)

// ============ Near Misses API (extracted: nearMissesClient.ts) ============
export const nearMissesApi = createNearMissesApi(api)

// ============ Policies API (extracted: policiesClient.ts) ============
export const policiesApi = createPoliciesApi(api)

// ============ Risks API (extracted: risksClient.ts) ============
export const risksApi = createRisksApi(api)

// ============ Audits API (extracted: auditsClient.ts) ============
export const auditsApi = createAuditsApi(api)

// ============ Workforce API (extracted: workforceClient.ts) ============
export const workforceApi = createWorkforceApi(api)
export const engineersApi = createEngineersApi(api)

// ============ Training Matrix API (Atlas compliance layer) ============
export const trainingMatrixApi = createTrainingMatrixApi(api)
export {
  ATLAS_HUB_URL,
  type TrainingMatrixComplianceRow,
  type TrainingMatrixImport,
  type TrainingMatrixImportQa,
  type TrainingMatrixRequirement,
  type TrainingMatrixNameMapItem,
  type TrainingMatrixMatrixCell,
  type TrainingMatrixMatrixUpsertResponse,
  type TrainingMatrixFrequencyChangeRequest,
  type TrainingMatrixFrequencyChangeRequestList,
  type TrainingMatrixNotifyResponse,
} from './trainingMatrixClient'

// ============ Portal tool + van compliance (person-scoped) ============
export const portalComplianceApi = createPortalComplianceApi(api)
export type {
  PortalClearState,
  PortalMyCompliance,
  PortalMyTools,
  PortalMyVan,
  PortalToolBand,
  PortalToolItem,
} from './portalComplianceClient'

// ============ Investigation Types (extracted: investigationsClient.ts) ============
export type {
  Investigation,
  InvestigationCreate,
  CreateFromRecordRequest,
  CreateFromRecordError,
  SourceRecordItem,
  SourceRecordsResponse,
  InvestigationUpdate,
  InvestigationAutosave,
  TimelineEvent,
  TimelineResponse,
  InvestigationComment,
  CommentsResponse,
  CustomerPackSummary,
  PacksResponse,
  GeneratedCustomerPack,
  ClosureValidation,
} from './investigationsClient'
export const investigationsApi = createInvestigationsApi(api)

export const standardsApi = createStandardsApi(api)

// ============ Actions API (extracted: actionsClient.ts) ============
export const actionsApi = createActionsApi(api)

export type {
  CarbonReportingYear,
  PlanetMarkDashboardResponse,
  PlanetMarkReportingYearRecord,
  PlanetMarkReportingYearsResponse,
  PlanetMarkEmissionSourceRecord,
  PlanetMarkEmissionSourcesResponse,
  PlanetMarkScope3CategoryRecord,
  PlanetMarkScope3Response,
  PlanetMarkActionRecord,
  PlanetMarkActionsResponse,
  PlanetMarkCertificationResponse,
  PlanetMarkDataQualityResponse,
  PlanetMarkEvidenceRecord,
  PlanetMarkEvidenceListResponse,
  PlanetMarkMsXlsxIngestResponse,
} from './planetMarkClient'
export const planetMarkApi = createPlanetMarkApi(api)

// UVDB types + API live in uvdbClient.ts (Path-to-10 S7)
export type {
  UVDBSectionRecord,
  UVDBQuestion,
  UVDBAuditListItem,
  UVDBAuditResponse,
  UVDBDashboardResponse,
  UVDBSectionsResponse,
  UVDBAuditsResponse,
  UVDBIsoMappingRecord,
  UVDBIsoMappingResponse,
} from './uvdbClient'
export const uvdbApi = createUvdbApi(api)


// ============ User API ============

// User type for search results
// ============ Users API (extracted: usersClient.ts) ============
export type {
  UserSearchResult,
  UserDetail,
  RoleDetail,
  UserCreatePayload,
  UserUpdatePayload,
  RoleCreatePayload,
  RoleUpdatePayload,
} from './usersClient'
export const usersApi = createUsersApi(api)

// ============ Audit Trail API (extracted: auditTrailClient.ts) ============
export type {
  AuditLogEntry,
  AuditVerification,
} from './auditTrailClient'
export const auditTrailApi = createAuditTrailApi(api)

// ============ Risk Register API (extracted: riskRegisterClient.ts) ============
export type {
  RiskEntry,
  RiskHeatmapData,
  RiskSummary,
} from './riskRegisterClient'
export const riskRegisterApi = createRiskRegisterApi(api)

// ============ Signatures API (extracted: signaturesClient.ts) ============
export type { SignatureRequestEntry } from './signaturesClient'
export const signaturesApi = createSignaturesApi(api)

// ============ AI Intelligence API ============

export const aiApi = {
  analyzeText: (text: string, analysisType?: string) =>
    api.post<unknown>('/api/v1/ai/analyze-text', {
      text,
      analysis_type: analysisType,
    }),
  getPredictions: (module?: string) =>
    api.get<unknown>(`/api/v1/ai/predictions${module ? `?module=${module}` : ''}`),
  getAnomalies: (module?: string, days?: number) =>
    api.get<unknown>(
      `/api/v1/ai/anomalies?${new URLSearchParams({ ...(module ? { module } : {}), ...(days ? { days: String(days) } : {}) })}`,
    ),
  auditAssistant: (query: string, context?: Record<string, unknown>) =>
    api.post<unknown>('/api/v1/ai/audit-assistant', { query, context }),
  getRecommendations: (module?: string) =>
    api.get<unknown>(`/api/v1/ai/recommendations${module ? `?module=${module}` : ''}`),
  getSentiment: (text: string) => api.post<unknown>('/api/v1/ai/sentiment', { text }),
  classifyRisk: (description: string) =>
    api.post<unknown>('/api/v1/ai/classify-risk', { description }),
  getDashboard: () => api.get<unknown>('/api/v1/ai/dashboard'),
  generateAuditQuestions: (standard: string, clause: string, context?: string) =>
    api.post<unknown[]>('/api/v1/ai/audit/generate-questions', {
      standard,
      clause,
      context,
    }),
  generateAuditChecklist: (standard: string, scopeClauses?: string[]) =>
    api.post<unknown[]>('/api/v1/ai/audit/generate-checklist', {
      standard,
      scope_clauses: scopeClauses,
    }),
}

// ============ Governance Calendar API ============

export type CalendarEventType = 'audit' | 'deadline' | 'review' | 'training' | 'meeting'

export interface CalendarFeedEvent {
  id: string
  title: string
  type: CalendarEventType
  date: string
  status: 'upcoming' | 'today' | 'overdue' | 'completed' | string
  priority?: 'high' | 'medium' | 'low' | string
  owner?: string | null
  source_module: string
  source_id: string
  href?: string | null
  description?: string | null
}

export interface CalendarFeedResponse {
  start: string
  end: string
  generated_at: string
  total: number
  events: CalendarFeedEvent[]
  sources_ok: string[]
  sources_failed: string[]
}

export const calendarApi = {
  getFeed: (params?: { start?: string; end?: string; types?: string[] }) => {
    const sp = new URLSearchParams()
    if (params?.start) sp.set('start', params.start)
    if (params?.end) sp.set('end', params.end)
    if (params?.types?.length) sp.set('types', params.types.join(','))
    const q = sp.toString()
    return api.get<CalendarFeedResponse>(`/api/v1/calendar/feed${q ? `?${q}` : ''}`)
  },
}

// ============ Analytics API ============

export const analyticsApi = {
  getKPIs: (timeRange?: string) =>
    api.get<unknown>(`/api/v1/analytics/kpis${timeRange ? `?time_range=${timeRange}` : ''}`),
  getTrends: (dataSource: string, timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/trends/${dataSource}${timeRange ? `?time_range=${timeRange}` : ''}`,
    ),
  getBenchmarks: (industry?: string) =>
    api.get<unknown>(`/api/v1/analytics/benchmarks${industry ? `?industry=${industry}` : ''}`),
  getExecutiveSummary: (timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/reports/executive-summary${timeRange ? `?time_range=${timeRange}` : ''}`,
    ),
  getNonComplianceCosts: (timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/costs/non-compliance${timeRange ? `?time_range=${timeRange}` : ''}`,
    ),
  getROI: () => api.get<unknown>('/api/v1/analytics/roi'),
  getCostBreakdown: (timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/costs/breakdown${timeRange ? `?time_range=${timeRange}` : ''}`,
    ),
  getDrillDown: (dataSource: string, dimension: string, value: string, timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/drill-down/${dataSource}?dimension=${dimension}&value=${value}${timeRange ? `&time_range=${timeRange}` : ''}`,
    ),
  forecast: (dataSource: string, metric: string, periodsAhead?: number) =>
    api.post<unknown>('/api/v1/analytics/forecast', {
      data_source: dataSource,
      metric,
      periods_ahead: periodsAhead || 12,
      confidence_level: 0.95,
    }),
  listDashboards: () =>
    api.get<{
      dashboards: Array<{
        id: number
        name: string
        description?: string
        icon?: string
        color?: string
        is_default?: boolean
        widget_count?: number
        updated_at?: string
      }>
    }>('/api/v1/analytics/dashboards'),
  getDashboard: (id: number) =>
    api.get<{
      id: number
      name: string
      description?: string
      widgets: Array<{
        id: number
        widget_type: string
        title: string
        data_source: string
        metric: string
        grid_x: number
        grid_y: number
        grid_w: number
        grid_h: number
      }>
    }>(`/api/v1/analytics/dashboards/${id}`),
  createDashboard: (data: { name: string; description?: string; widgets?: unknown[] }) =>
    api.post<{ id: number; name: string }>('/api/v1/analytics/dashboards', data),
  updateDashboard: (id: number, data: { name?: string; description?: string; layout?: unknown }) =>
    api.put<{ id: number; name: string }>(`/api/v1/analytics/dashboards/${id}`, data),
  deleteDashboard: (id: number) =>
    api.delete<{ success: boolean }>(`/api/v1/analytics/dashboards/${id}`),
  getWidgetData: (widgetId: number, timeRange?: string) =>
    api.get<unknown>(
      `/api/v1/analytics/widgets/${widgetId}/data${timeRange ? `?time_range=${timeRange}` : ''}`,
    ),
}

// ============ Notifications API (extracted: notificationsClient.ts) ============
export type {
  NotificationEntry,
  NotificationCategoryChannels,
  NotificationDeliveryStatus,
  NotificationPreferences,
} from './notificationsClient'
export const notificationsApi = createNotificationsApi(api)

// ============ Compliance API ============

export interface AutoTagResult {
  clause_id: string
  clause_number: string
  title: string
  standard: string
  confidence: number
  linked_by: string
  evidence_snippet?: string
  evidence_quality?: string
  evidence_quality_code?: string
}

export interface MultiStageAnalysisResult {
  analyzed_at: string
  content_length: number
  total_clauses_matched: number
  standards_covered: string[]
  primary_results: AutoTagResult[]
  stages: {
    stage_1_keyword?: { method: string; candidates: number; results: AutoTagResult[] }
    stage_2_ai?: { method: string; model?: string; results?: AutoTagResult[]; error?: string }
    stage_3_cross_standard?: { cross_standard_matches: unknown[]; standards_covered: string[] }
    stage_4_quality?: { results: AutoTagResult[] }
    stage_5_conformance?: { conformance_statement?: string; clauses_addressed?: string[]; error?: string; skipped?: string }
  }
}

export interface SoAControl {
  control_id: string
  clause_id: string
  title: string
  description: string
  applicable: boolean
  implementation_status: 'Implemented' | 'Partially Implemented' | 'Not Implemented'
  evidence_count: number
  evidence: { entity_type: string; entity_id: string; title: string; linked_by: string; confidence?: number }[]
  justification: string
}

export interface StatementOfApplicability {
  document_type: string
  standard: string
  organization: string
  generated_at: string
  version: string
  total_controls: number
  statistics: { applicable: number; implemented: number; partial: number; not_implemented: number; excluded: number }
  controls: SoAControl[]
  summary: string
  persisted_evidence_links: number
}

export interface EvidenceLinkRecord {
  id: number
  entity_type: string
  entity_id: string
  clause_id: string
  linked_by: string
  confidence: number | null
  title: string | null
  notes: string | null
  created_at: string
  created_by_email: string | null
}

export interface ComplianceClauseRecord {
  id: string
  standard: string
  clause_number: string
  title: string
  description: string
  keywords: string[]
  parent_clause?: string | null
  level: number
}

export interface ComplianceCoverageResponse {
  total_clauses: number
  full_coverage: number
  partial_coverage: number
  gaps: number
  coverage_percentage: number
  gap_clauses?: Array<{
    clause_id: string
    clause_number: string
    title: string
    standard: string
  }>
  by_standard?: Record<
    string,
    {
      total: number
      covered: number
      partial_coverage: number
      gaps: number
      percentage: number
    }
  >
}

export interface ComplianceReportResponse {
  generated_at: string
  summary: ComplianceCoverageResponse
  persisted_evidence_links: number
  clauses: Array<{
    clause_id: string
    clause_number: string
    title: string
    description: string
    standard: string
    status: 'full' | 'partial' | 'gap'
    evidence_count: number
    evidence?: Array<{
      entity_type: string
      entity_id: string
      linked_by: string
      confidence?: number | null
    }>
  }>
}

export interface ComplianceStandardRecord {
  id: string
  code: string
  name: string
  description: string
  clause_count: number
  db_standard_id?: number | null
  db_standard_code?: string | null
  db_standard_name?: string | null
  db_clause_count: number
  ims_requirement_count: number
  covered_clauses: number
  coverage_percentage: number
  has_canonical_standard: boolean
  canonical_data_degraded?: boolean
  canonical_data_message?: string | null
}

export interface CrossStandardMappingRecord {
  id: number
  primary_standard: string
  primary_clause: string
  mapped_standard: string
  mapped_clause: string
  mapping_type: string
  mapping_strength: number
  mapping_notes?: string | null
  annex_sl_element?: string | null
}

export const complianceApi = {
  listClauses: (standard?: string, search?: string) => {
    const sp = new URLSearchParams()
    if (standard) sp.set('standard', standard)
    if (search) sp.set('search', search)
    return api.get<ComplianceClauseRecord[]>(`/api/v1/compliance/clauses?${sp}`)
  },
  autoTag: (content: string, useAi = false) =>
    api.post<AutoTagResult[]>('/api/v1/compliance/auto-tag', {
      content,
      use_ai: useAi,
    }),
  linkEvidence: (data: {
    entity_type: string
    entity_id: string
    clause_ids: string[]
    linked_by?: string
    confidence?: number
    title?: string
    notes?: string
  }) =>
    api.post<{ status: string; message: string; links: unknown[] }>(
      '/api/v1/compliance/evidence/link',
      data,
    ),
  listEvidenceLinks: (params?: {
    entity_type?: string
    entity_id?: string
    clause_id?: string
    page?: number
    size?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.entity_type) sp.set('entity_type', params.entity_type)
    if (params?.entity_id) sp.set('entity_id', params.entity_id)
    if (params?.clause_id) sp.set('clause_id', params.clause_id)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.size) sp.set('size', String(params.size))
    return api.get<EvidenceLinkRecord[]>(`/api/v1/compliance/evidence/links?${sp}`)
  },
  deleteEvidenceLink: (linkId: number) =>
    api.delete<{ status: string }>(`/api/v1/compliance/evidence/link/${linkId}`),
  getCoverage: (standard?: string) =>
    api.get<ComplianceCoverageResponse>(
      `/api/v1/compliance/coverage${standard ? `?standard=${standard}` : ''}`,
    ),
  getGaps: (standard?: string) =>
    api.get<{ total_gaps: number; gap_clauses: unknown[] }>(
      `/api/v1/compliance/gaps${standard ? `?standard=${standard}` : ''}`,
    ),
  getReport: (standard?: string) =>
    api.get<ComplianceReportResponse>(
      `/api/v1/compliance/report${standard ? `?standard=${standard}` : ''}`,
    ),
  /**
   * Server-side ISO audit pack with full CEL provenance.
   * Defaults to excluding nonconformity/gap/opportunity from conformance evidence.
   */
  downloadAuditPack: (params?: {
    standard?: string
    includeNonconformity?: boolean
    includeSoa?: boolean
    organizationName?: string
  }) => {
    const sp = new URLSearchParams()
    if (params?.standard) sp.set('standard', params.standard)
    if (params?.includeNonconformity) sp.set('include_nonconformity', 'true')
    if (params?.includeSoa === false) sp.set('include_soa', 'false')
    if (params?.organizationName) sp.set('organization_name', params.organizationName)
    const qs = sp.toString()
    return api.get<Record<string, unknown>>(`/api/v1/compliance/audit-pack${qs ? `?${qs}` : ''}`)
  },
  listStandards: () => api.get<ComplianceStandardRecord[]>('/api/v1/compliance/standards'),
  /**
   * 5-stage Genspark-powered evidence analysis.
   * Returns keyword + LLM mapping, cross-standard links, quality scores,
   * and an auditor conformance statement.
   */
  analyzeEvidence: (content: string) =>
    api.post<MultiStageAnalysisResult>('/api/v1/compliance/analyze', {
      content,
      use_ai: true,
      min_confidence: 50,
    }),
  /** Generate ISO 27001:2022 Statement of Applicability from persisted evidence */
  getSoA: (organizationName?: string) => {
    const sp = new URLSearchParams()
    if (organizationName) sp.set('organization_name', organizationName)
    return api.get<StatementOfApplicability>(`/api/v1/compliance/soa?${sp}`)
  },
}

export const crossStandardMappingsApi = {
  list: (params?: {
    source_standard?: string
    target_standard?: string
    clause?: string
    limit?: number
    offset?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.source_standard) sp.set('source_standard', params.source_standard)
    if (params?.target_standard) sp.set('target_standard', params.target_standard)
    if (params?.clause) sp.set('clause', params.clause)
    if (params?.limit != null) sp.set('limit', String(params.limit))
    if (params?.offset != null) sp.set('offset', String(params.offset))
    return api.get<CrossStandardMappingRecord[]>(`/api/v1/cross-standard-mappings?${sp}`)
  },
  listStandards: () =>
    api.get<{
      standards: string[]
    }>('/api/v1/cross-standard-mappings/standards'),
}

// ============ Compliance Automation API ============

export const complianceAutomationApi = {
  listRegulatoryUpdates: (params?: { source?: string; impact?: string; reviewed?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.source) sp.set('source', params.source)
    if (params?.impact) sp.set('impact', params.impact)
    if (params?.reviewed !== undefined) sp.set('reviewed', String(params.reviewed))
    return api.get<{ updates: unknown[]; total: number; unreviewed: number }>(
      `/api/v1/compliance-automation/regulatory-updates?${sp}`,
    )
  },
  reviewUpdate: (updateId: number, data?: { requires_action?: boolean; action_notes?: string }) => {
    const sp = new URLSearchParams()
    if (data?.requires_action !== undefined) sp.set('requires_action', String(data.requires_action))
    if (data?.action_notes) sp.set('action_notes', data.action_notes)
    return api.post<unknown>(
      `/api/v1/compliance-automation/regulatory-updates/${updateId}/review?${sp}`,
    )
  },
  runGapAnalysis: (params?: { regulatory_update_id?: number; standard_id?: number }) => {
    const sp = new URLSearchParams()
    if (params?.regulatory_update_id)
      sp.set('regulatory_update_id', String(params.regulatory_update_id))
    if (params?.standard_id) sp.set('standard_id', String(params.standard_id))
    return api.post<unknown>(`/api/v1/compliance-automation/gap-analysis/run?${sp}`)
  },
  listGapAnalyses: (status?: string) => {
    const sp = new URLSearchParams()
    if (status) sp.set('status', status)
    return api.get<{ analyses: unknown[]; total: number }>(
      `/api/v1/compliance-automation/gap-analyses?${sp}`,
    )
  },
  listCertificates: (params?: {
    certificate_type?: string
    entity_type?: string
    status?: string
    expiring_within_days?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.certificate_type) sp.set('certificate_type', params.certificate_type)
    if (params?.entity_type) sp.set('entity_type', params.entity_type)
    if (params?.status) sp.set('status', params.status)
    if (params?.expiring_within_days)
      sp.set('expiring_within_days', String(params.expiring_within_days))
    return api.get<{ certificates: unknown[]; total: number }>(
      `/api/v1/compliance-automation/certificates?${sp}`,
    )
  },
  getAssuranceCertShelf: (params?: {
    scheme?: string
    readiness_status?: string
    due_soon_days?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.scheme) sp.set('scheme', params.scheme)
    if (params?.readiness_status) sp.set('readiness_status', params.readiness_status)
    if (params?.due_soon_days) sp.set('due_soon_days', String(params.due_soon_days))
    return api.get<AssuranceCertShelfResponse>(`/api/v1/compliance-automation/certificates/shelf?${sp}`)
  },
  getExpiringCertificates: () =>
    api.get<{
      expired: number
      expiring_7_days: number
      expiring_30_days: number
      expiring_90_days: number
      total_critical: number
    }>('/api/v1/compliance-automation/certificates/expiring-summary'),
  addCertificate: (data: {
    name: string
    certificate_type: string
    entity_type: string
    entity_id: string
    entity_name?: string
    issuing_body?: string
    issue_date: string
    expiry_date: string
    is_critical?: boolean
    notes?: string
  }) => api.post<unknown>('/api/v1/compliance-automation/certificates', data),
  listScheduledAudits: (params?: { upcoming_days?: number; overdue?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.upcoming_days) sp.set('upcoming_days', String(params.upcoming_days))
    if (params?.overdue !== undefined) sp.set('overdue', String(params.overdue))
    return api.get<{ audits: unknown[]; total: number }>(
      `/api/v1/compliance-automation/scheduled-audits?${sp}`,
    )
  },
  scheduleAudit: (data: {
    name: string
    audit_type: string
    frequency: string
    next_due_date: string
    description?: string
    department?: string
    standard_ids?: string[]
  }) => api.post<unknown>('/api/v1/compliance-automation/scheduled-audits', data),
  getComplianceScore: (params?: { scope_type?: string; scope_id?: string }) => {
    const sp = new URLSearchParams()
    if (params?.scope_type) sp.set('scope_type', params.scope_type)
    if (params?.scope_id) sp.set('scope_id', params.scope_id)
    return api.get<Record<string, unknown>>(`/api/v1/compliance-automation/score?${sp}`)
  },
  getComplianceTrend: (params?: { scope_type?: string; months?: number }) => {
    const sp = new URLSearchParams()
    if (params?.scope_type) sp.set('scope_type', params.scope_type)
    if (params?.months) sp.set('months', String(params.months))
    return api.get<{ trend: unknown[]; period_months: number }>(
      `/api/v1/compliance-automation/score/trend?${sp}`,
    )
  },
  listRiddorSubmissions: (status?: string) => {
    const sp = new URLSearchParams()
    if (status) sp.set('status_filter', status)
    return api.get<{ submissions: unknown[]; total: number }>(
      `/api/v1/compliance-automation/riddor/submissions?${sp}`,
    )
  },
  checkRiddor: (incidentData: Record<string, unknown>) =>
    api.post<{
      is_riddor: boolean
      riddor_types: string[]
      deadline: string | null
      submission_url: string | null
    }>('/api/v1/compliance-automation/riddor/check', incidentData),
  prepareRiddor: (incidentId: number, riddorType: string) => {
    const sp = new URLSearchParams({ riddor_type: riddorType })
    return api.post<unknown>(`/api/v1/compliance-automation/riddor/prepare/${incidentId}?${sp}`)
  },
  submitRiddor: (incidentId: number) =>
    api.post<unknown>(`/api/v1/compliance-automation/riddor/submit/${incidentId}`),
}

// ============ IMS Dashboard API ============

export interface IMSDashboardResponse {
  generated_at: string
  overall_compliance: number
  standards: {
    standard_id: number
    standard_code: string
    standard_name: string
    full_name: string
    version: string
    total_controls: number
    implemented_count: number
    partial_count: number
    not_implemented_count: number
    compliance_percentage: number
    setup_required: boolean
  }[]
  isms: {
    assets: { total: number; critical: number }
    controls: {
      total: number
      applicable: number
      implemented: number
      implementation_percentage: number
    }
    risks: { open: number; high_critical: number }
    incidents: { open: number; last_30_days: number }
    suppliers: { high_risk: number }
    compliance_score: number
    domains: {
      domain: string
      total: number
      implemented: number
      percentage: number
    }[]
    recent_incidents: {
      id: string
      title: string
      incident_type: string
      severity: string
      status: string
      date: string
    }[]
  } | null
  isms_error?: string
  uvdb: {
    total_audits: number
    active_audits: number
    completed_audits: number
    average_score: number
    latest_score: number | null
    status: string
  } | null
  uvdb_error?: string
  planet_mark: {
    status: string
    current_year: number | null
    total_emissions: number | null
    certification_status: string | null
    reduction_vs_previous: number | null
    scope1: number
    scope2: number
    scope3: number
  } | null
  planet_mark_error?: string
  compliance_coverage: {
    total_clauses: number
    covered_clauses: number
    coverage_percentage: number
    gaps: number
    total_evidence_links: number
  } | null
  compliance_coverage_error?: string
  audit_schedule: {
    id: number
    reference_number: string
    title: string | null
    status: string
    scheduled_date: string | null
    due_date: string | null
  }[]
  audit_schedule_error?: string
  standards_error?: string
}

export const imsDashboardApi = {
  getDashboard: () => api.get<IMSDashboardResponse>('/api/v1/ims/dashboard'),
}

export interface LibraryDashboardSummary {
  as_of: string
  statutory_documents: number
  overdue_reviews: number
  open_review_packs: number
}

export interface LibraryDependencyMap {
  pel_doc_ref: string
  document_id: number
  title: string
  current_tip: {
    version_number: string
    status: string
    published_at?: string | null
  }
  superseded_history: {
    id: number
    version_number: string
    status: string
    published_at?: string | null
    change_notes?: string | null
  }[]
}

export const libraryReviewApi = {
  getDashboardSummary: () => api.get<LibraryDashboardSummary>('/api/v1/library-review/dashboard-summary'),
  getDependencyMap: (pelDocRef: string) =>
    api.get<LibraryDependencyMap>(`/api/v1/library-review/dependencies/${encodeURIComponent(pelDocRef)}`),
}

// ============ ISO 27001 ISMS API ============

export interface IsmsApiDashboard {
  assets: { total: number; critical: number }
  controls: { total: number; applicable: number; implemented: number; implementation_percentage: number }
  risks: { open: number; high_critical: number }
  incidents: { open: number; last_30_days: number }
  suppliers: { high_risk: number }
  compliance_score: number
  domains: { domain: string; total: number; implemented: number; percentage: number }[]
  recent_incidents: {
    id: string
    title: string
    incident_type: string
    severity: string
    status: string
    date: string | null
  }[]
}

export interface AssetCreatePayload {
  name: string
  asset_type: 'hardware' | 'software' | 'data' | 'service' | 'people' | 'physical'
  classification?: 'public' | 'internal' | 'confidential' | 'restricted' | 'secret'
  criticality?: 'low' | 'medium' | 'high' | 'critical'
  description?: string
  owner_name?: string
  department?: string
  location?: string
  confidentiality_requirement?: number
  integrity_requirement?: number
  availability_requirement?: number
}

export interface RiskCreatePayload {
  title: string
  description: string
  threat_source?: string
  likelihood?: number
  impact?: number
  residual_likelihood?: number
  residual_impact?: number
  treatment_option?: 'accept' | 'avoid' | 'mitigate' | 'transfer'
  treatment_plan?: string
  risk_owner_name?: string
}

export interface IncidentCreatePayload {
  title: string
  description: string
  incident_type: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
  priority?: 'low' | 'medium' | 'high' | 'critical'
  detected_date: string
  occurred_date?: string
  cia_impact?: string[]
  data_compromised?: boolean
  regulatory_notification_required?: boolean
  reported_by_name?: string
}

export interface SupplierCreatePayload {
  supplier_name: string
  supplier_type: string
  overall_rating: 'compliant' | 'partially_compliant' | 'non_compliant'
  risk_level?: 'low' | 'medium' | 'high' | 'critical'
  data_access_level?: 'none' | 'limited' | 'full'
  services_provided?: string
  security_score?: number
  iso27001_certified?: boolean
  soc2_certified?: boolean
  findings_count?: number
  critical_findings?: number
  assessment_frequency_months?: number
}

export interface AccessControlCreatePayload {
  user_id: number
  user_name: string
  user_email?: string
  user_department?: string
  system_name: string
  access_level: 'read' | 'write' | 'admin' | 'owner'
  granted_date: string
  granted_by?: string
  expiry_date?: string
}

export interface BCPCreatePayload {
  name: string
  description: string
  scope: string
  rto_hours: number
  rpo_hours: number
  mtpd_hours?: number
  effective_date: string
  version?: string
  plan_owner_name?: string
  activation_criteria?: string
  test_frequency_months?: number
}

export const iso27001Api = {
  getDashboard: () => api.get<IsmsApiDashboard>('/api/v1/iso27001/dashboard'),

  // Assets
  getAssets: (params?: { skip?: number; limit?: number; criticality?: string; asset_type?: string }) =>
    api.get<{ total: number; assets: unknown[] }>('/api/v1/iso27001/assets', { params }),
  getAsset: (assetId: number) =>
    api.get<Record<string, unknown>>(`/api/v1/iso27001/assets/${assetId}`),
  createAsset: (payload: AssetCreatePayload) =>
    api.post<{ id: number; asset_id: string; message: string }>('/api/v1/iso27001/assets', payload),
  updateAsset: (assetId: number, payload: Partial<AssetCreatePayload> & { status?: string }) =>
    api.put<{ id: number; message: string }>(`/api/v1/iso27001/assets/${assetId}`, payload),

  // Controls
  getControls: (params?: { domain?: string; implementation_status?: string; is_applicable?: boolean }) =>
    api.get<{ total: number; summary: unknown; controls: unknown[] }>('/api/v1/iso27001/controls', { params }),
  updateControl: (
    controlId: number,
    payload: {
      implementation_status?: 'not_implemented' | 'partial' | 'implemented' | 'excluded'
      implementation_notes?: string
      is_applicable?: boolean
      exclusion_justification?: string
      effectiveness_rating?: string
      control_owner_name?: string
    },
  ) => api.put<{ id: number; message: string }>(`/api/v1/iso27001/controls/${controlId}`, payload),

  // SoA
  getSoa: () =>
    api.get<{ version: string; status: string; implementation_percentage: number; id?: number; approved_by?: string; effective_date?: string }>('/api/v1/iso27001/soa'),

  // Risks
  getRisks: (params?: { skip?: number; limit?: number; min_score?: number; status?: string; include_closed?: boolean }) =>
    api.get<{ total: number; risks: unknown[] }>('/api/v1/iso27001/risks', { params }),
  getRisk: (riskId: number) =>
    api.get<Record<string, unknown>>(`/api/v1/iso27001/risks/${riskId}`),
  createRisk: (payload: RiskCreatePayload) =>
    api.post<{ id: number; risk_id: string; message: string }>('/api/v1/iso27001/risks', payload),
  updateRisk: (riskId: number, payload: Partial<RiskCreatePayload> & { status?: string; treatment_status?: string }) =>
    api.put<{ id: number; message: string }>(`/api/v1/iso27001/risks/${riskId}`, payload),

  // Incidents
  getIncidents: (params?: { skip?: number; limit?: number; severity?: string; status?: string }) =>
    api.get<{ total: number; open_incidents: number; critical_incidents: number; incidents: unknown[] }>('/api/v1/iso27001/incidents', { params }),
  getIncident: (incidentId: number) =>
    api.get<Record<string, unknown>>(`/api/v1/iso27001/incidents/${incidentId}`),
  createIncident: (payload: IncidentCreatePayload) =>
    api.post<{ id: number; incident_id: string; message: string }>('/api/v1/iso27001/incidents', payload),
  updateIncident: (
    incidentId: number,
    payload: {
      status?: 'open' | 'investigating' | 'contained' | 'eradicating' | 'recovering' | 'closed'
      severity?: string
      assigned_to_name?: string
      root_cause?: string
      containment_actions?: string
      eradication_actions?: string
      recovery_actions?: string
      lessons_learned?: string
      regulatory_notification_required?: boolean
      regulatory_body?: string
    },
  ) => api.put<{ id: number; message: string }>(`/api/v1/iso27001/incidents/${incidentId}`, payload),

  // Suppliers
  getSuppliers: (params?: { skip?: number; limit?: number; risk_level?: string; rating?: string }) =>
    api.get<{ total: number; suppliers: unknown[] }>('/api/v1/iso27001/suppliers', { params }),
  getSupplier: (supplierId: number) =>
    api.get<Record<string, unknown>>(`/api/v1/iso27001/suppliers/${supplierId}`),
  createSupplier: (payload: SupplierCreatePayload) =>
    api.post<{ id: number; message: string }>('/api/v1/iso27001/suppliers', payload),

  // Access Control
  getAccessControl: (params?: { active_only?: boolean; skip?: number; limit?: number }) =>
    api.get<{ total: number; overdue_reviews: number; records: unknown[] }>('/api/v1/iso27001/access-control', { params }),
  createAccessControl: (payload: AccessControlCreatePayload) =>
    api.post<{ id: number; message: string }>('/api/v1/iso27001/access-control', payload),

  // Business Continuity Plans
  getBCPs: (params?: { active_only?: boolean; skip?: number; limit?: number }) =>
    api.get<{ total: number; plans: unknown[] }>('/api/v1/iso27001/business-continuity', { params }),
  getBCP: (planId: number) =>
    api.get<Record<string, unknown>>(`/api/v1/iso27001/business-continuity/${planId}`),
  createBCP: (payload: BCPCreatePayload) =>
    api.post<{ id: number; plan_id: string; message: string }>('/api/v1/iso27001/business-continuity', payload),
  updateBCP: (planId: number, payload: Partial<BCPCreatePayload> & { is_active?: boolean; last_test_date?: string; last_test_type?: string; last_test_result?: string }) =>
    api.put<{ id: number; message: string }>(`/api/v1/iso27001/business-continuity/${planId}`, payload),
}

// ============ Global Search API ============

export const searchApi = {
  search: (
    queryOrParams:
      | string
      | {
          q: string
          module?: string
          type?: string
          status?: string
          date_from?: string
          date_to?: string
          page?: number
          page_size?: number
        },
    filters?: {
      module?: string
      type?: string
      status?: string
      date_from?: string
      date_to?: string
    },
  ) => {
    const params =
      typeof queryOrParams === 'string' ? { q: queryOrParams, ...filters } : queryOrParams

    const sp = new URLSearchParams({ q: params.q })
    if (params.module) sp.set('module', params.module)
    if (params.type) sp.set('type', params.type)
    if (params.status) sp.set('status', params.status)
    if (params.date_from) sp.set('date_from', params.date_from)
    if (params.date_to) sp.set('date_to', params.date_to)
    if (params.page) sp.set('page', String(params.page))
    if (params.page_size) sp.set('page_size', String(params.page_size))
    return api.get<GlobalSearchResponse>(`/api/v1/search?${sp}`)
  },
}

// ============ Evidence Assets API ============

export interface EvidenceAsset {
  id: number
  storage_key: string
  original_filename?: string
  content_type: string
  file_size_bytes?: number
  checksum_sha256?: string
  asset_type: string
  source_module: string
  source_id: number
  linked_investigation_id?: number
  title?: string
  description?: string
  captured_at?: string
  captured_by_role?: string
  latitude?: number
  longitude?: number
  location_description?: string
  render_hint?: string
  thumbnail_storage_key?: string
  metadata_json?: Record<string, unknown>
  visibility: string
  contains_pii: boolean
  redaction_required: boolean
  retention_policy: string
  retention_expires_at?: string
  created_at: string
  updated_at: string
  created_by_id?: number
  updated_by_id?: number
}

export interface EvidenceAssetListResponse {
  items: EvidenceAsset[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface EvidenceAssetUploadResponse {
  id: number
  storage_key: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  upload_url?: string
  message: string
}

export interface SignedUrlResponse {
  asset_id: number
  signed_url: string
  expires_in_seconds: number
  content_type: string
  filename?: string
}

export const evidenceAssetsApi = {
  /**
   * List evidence assets with filtering.
   * For investigations: source_module=investigation, source_id=investigation_id
   */
  list: (options?: {
    page?: number
    page_size?: number
    source_module?: string
    source_id?: number
    action_key?: string
    asset_type?: string
    linked_investigation_id?: number
  }) => {
    const params = new URLSearchParams()
    if (options?.page) params.set('page', String(options.page))
    if (options?.page_size) params.set('page_size', String(options.page_size))
    if (options?.source_module) params.set('source_module', options.source_module)
    if (options?.source_id != null) params.set('source_id', String(options.source_id))
    if (options?.action_key) params.set('action_key', options.action_key)
    if (options?.asset_type) params.set('asset_type', options.asset_type)
    if (options?.linked_investigation_id)
      params.set('linked_investigation_id', String(options.linked_investigation_id))
    return api.get<EvidenceAssetListResponse>(`/api/v1/evidence-assets/?${params}`)
  },

  /**
   * Get a single evidence asset by ID.
   */
  get: (assetId: number) => api.get<EvidenceAsset>(`/api/v1/evidence-assets/${assetId}`),

  /**
   * Upload a new evidence asset.
   * Uses multipart/form-data for file upload.
   */
  upload: (
    file: File,
    data: {
      source_module: string
      source_id?: number
      action_key?: string
      title?: string
      description?: string
      visibility?: string
      contains_pii?: boolean
      redaction_required?: boolean
    },
  ) => {
    const sourceId =
      data.source_id !== undefined && data.source_id !== null
        ? data.source_id
        : data.action_key
          ? 0
          : (() => {
              throw new Error('Evidence upload requires source_id or action_key')
            })()
    const formData = new FormData()
    formData.append('file', file)
    formData.append('source_module', data.source_module)
    formData.append('source_id', String(sourceId))
    if (data.action_key) formData.append('action_key', data.action_key)
    if (data.title) formData.append('title', data.title)
    if (data.description) formData.append('description', data.description)
    if (data.visibility) formData.append('visibility', data.visibility)
    if (data.contains_pii !== undefined) formData.append('contains_pii', String(data.contains_pii))
    if (data.redaction_required !== undefined)
      formData.append('redaction_required', String(data.redaction_required))

    return api.post<EvidenceAssetUploadResponse>('/api/v1/evidence-assets/upload', formData, {
      timeout: UPLOAD_TIMEOUT_MS, // Extended timeout for file uploads to Azure Blob Storage
    })
  },

  /**
   * Link an evidence asset to an investigation.
   */
  linkToInvestigation: (assetId: number, investigationId: number) =>
    api.post<EvidenceAsset>(
      `/api/v1/evidence-assets/${assetId}/link-investigation?investigation_id=${investigationId}`,
    ),

  /**
   * Delete (soft delete) an evidence asset.
   */
  delete: (assetId: number) => api.delete(`/api/v1/evidence-assets/${assetId}`),

  /**
   * Get a signed download URL for an evidence asset.
   */
  getSignedUrl: (
    assetId: number,
    expiresIn?: number,
    disposition: 'attachment' | 'inline' = 'attachment',
  ) => {
    const params = new URLSearchParams()
    if (expiresIn) params.set('expires_in', String(expiresIn))
    params.set('disposition', disposition)
    return api.get<SignedUrlResponse>(`/api/v1/evidence-assets/${assetId}/signed-url?${params}`)
  },
}

// ============ Global Search Types ============

export interface GlobalSearchResultRecord {
  id: string
  type: 'incident' | 'rta' | 'complaint' | 'risk' | 'audit' | 'action' | 'document'
  title: string
  description: string
  module: string
  status: string
  date: string
  relevance: number
  highlights: string[]
}

export interface GlobalSearchResponse {
  results: GlobalSearchResultRecord[]
  total: number
  query: string
  facets: {
    modules: Record<string, number>
  }
}

// ============ Workflows API (extracted: workflowsClient.ts) ============
export type {
  WorkflowApprovalRecord,
  WorkflowInstanceRecord,
  WorkflowTemplateRecord,
  WorkflowDelegationRecord,
  WorkflowStatsResponse,
} from './workflowsClient'
export const workflowsApi = createWorkflowsApi(api)

// ============ Executive Dashboard ============

export interface ExecutiveDashboardData {
  generated_at: string
  period_days: number
  health_score: {
    score: number
    status: string
    color: string
    components: Record<string, number>
  }
  incidents: {
    total_in_period: number
    open: number
    by_severity: Record<string, number>
    sif_count: number
    psif_count: number
    critical_high: number
  }
  near_misses: {
    total_in_period: number
    previous_period: number
    trend_percent: number
    reporting_rate: string
  }
  complaints: {
    total_in_period: number
    open: number
    closed_in_period: number
    resolution_rate: number
  }
  rtas: {
    total_in_period: number
  }
  risks: {
    total_active: number
    by_level: Record<string, number>
    high_critical: number
    average_score: number
  }
  kris: {
    total_active: number
    by_status: Record<string, number>
    at_risk: number
    pending_alerts: number
  }
  compliance: {
    total_assigned: number
    completed: number
    overdue: number
    completion_rate: number
  }
  sla_performance: {
    total_tracked: number
    met: number
    breached: number
    compliance_rate: number
  }
  trends: {
    incidents_weekly: { week_start: string; count: number; value?: number | null }[]
    complaints_weekly?: { week_start: string; count: number; value?: number | null }[]
    near_misses_weekly?: { week_start: string; count: number; value?: number | null }[]
    audits_weekly?: { week_start: string; count: number; value?: number | null }[]
    training_compliance_weekly?: { week_start: string; count: number; value?: number | null }[]
    tool_compliance_weekly?: { week_start: string; count: number; value?: number | null }[]
  }
  alerts: {
    type: string
    severity: string
    title: string
    triggered_at: string
  }[]
}

export const executiveDashboardApi = {
  getDashboard: (periodDays = 30) =>
    api.get<ExecutiveDashboardData>(`/api/v1/executive-dashboard?period_days=${periodDays}`),
  getSummary: () =>
    api.get<{
      health_score: number
      health_status: string
      open_incidents: number
      pending_actions: number
      overdue_items: number
      kri_alerts: number
    }>('/api/v1/executive-dashboard/summary'),
  getAlerts: () =>
    api.get<{ total: number; alerts: ExecutiveDashboardData['alerts'] }>(
      '/api/v1/executive-dashboard/alerts',
    ),
}

// ============ Report/Pack Capability Check ============

/**
 * Check if pack generation is available for an investigation.
 * Returns capability info for deterministic UI behavior.
 */
export interface PackCapability {
  canGenerate: boolean
  reason?: string
  lastError?: string
}

export async function checkPackCapability(investigationId: number): Promise<PackCapability> {
  try {
    // Try to hit the endpoint with a dry-run or just check if it returns 404/501
    // For now, we'll just try to get packs list - if that works, generation should too
    await investigationsApi.getPacks(investigationId, {
      page: 1,
      page_size: 1,
    })
    return { canGenerate: true }
  } catch (err: unknown) {
    const error = err as { response?: { status?: number } }
    if (error.response?.status === 404) {
      return {
        canGenerate: false,
        reason: 'Investigation not found or pack generation not available',
      }
    }
    if (error.response?.status === 501) {
      return {
        canGenerate: false,
        reason: 'Pack generation is not implemented in this environment',
      }
    }
    if (error.response?.status === 403) {
      return {
        canGenerate: false,
        reason: 'You do not have permission to generate packs',
      }
    }
    return { canGenerate: true } // Assume available, will fail on actual generate
  }
}

// ============ Admin Config Types (migrated from services/api.ts) ============

export interface FormFieldOption {
  value: string
  label: string
  sublabel?: string
}

export interface FormField {
  id: number
  name: string
  label: string
  field_type: string
  order: number
  placeholder?: string
  help_text?: string
  is_required: boolean
  min_length?: number
  max_length?: number
  min_value?: number
  max_value?: number
  pattern?: string
  default_value?: string
  options?: FormFieldOption[]
  show_condition?: Record<string, unknown>
  width: string
}

export interface FormStep {
  id: number
  name: string
  description?: string
  order: number
  icon?: string
  fields: FormField[]
  show_condition?: Record<string, unknown>
}

export interface FormTemplate {
  id: number
  name: string
  slug: string
  description?: string
  form_type: string
  version: number
  is_active: boolean
  is_published: boolean
  icon?: string
  color?: string
  allow_drafts: boolean
  allow_attachments: boolean
  require_signature: boolean
  auto_assign_reference: boolean
  reference_prefix?: string
  notify_on_submit: boolean
  steps: FormStep[]
  steps_count?: number
  fields_count?: number
  updated_at?: string
}

export interface Contract {
  id: number
  name: string
  code: string
  description?: string
  client_name?: string
  client_contact?: string
  client_email?: string
  is_active: boolean
  display_order: number
}

export type { LookupOption } from './lookupsClient'

export interface SystemSetting {
  key: string
  value: string
  category: string
  description?: string
  value_type: string
  is_editable?: boolean
}

// ============ Admin Config API (migrated from services/api.ts) ============
// These return data directly (not AxiosResponse) for compatibility with existing consumers.

export const formTemplatesApi = {
  list: (formType?: string) =>
    api
      .get<{
        items: FormTemplate[]
        total: number
      }>(`/api/v1/admin/config/templates${formType ? `?form_type=${formType}` : ''}`)
      .then((r) => r.data),

  getById: (id: number) =>
    api.get<FormTemplate>(`/api/v1/admin/config/templates/${id}`).then((r) => r.data),

  getBySlug: (slug: string) =>
    api.get<FormTemplate>(`/api/v1/admin/config/templates/by-slug/${slug}`).then((r) => r.data),

  create: (data: Partial<FormTemplate>) =>
    api.post<FormTemplate>('/api/v1/admin/config/templates', data).then((r) => r.data),

  update: (id: number, data: Partial<FormTemplate>) =>
    api.patch<FormTemplate>(`/api/v1/admin/config/templates/${id}`, data).then((r) => r.data),

  publish: (id: number) =>
    api.post<FormTemplate>(`/api/v1/admin/config/templates/${id}/publish`).then((r) => r.data),

  delete: (id: number) =>
    api.delete<void>(`/api/v1/admin/config/templates/${id}`).then((r) => r.data),
}

const ADMIN_CONFIG_SILENT = { suppressErrorToast: true } as const

export const contractsApi = {
  list: (activeOnly = true) =>
    api
      .get<{
        items: Contract[]
        total: number
      }>(
        `/api/v1/admin/config/contracts${activeOnly ? '?is_active=true' : ''}`,
        ADMIN_CONFIG_SILENT,
      )
      .then((r) => r.data),

  create: (data: Partial<Contract>) =>
    api
      .post<Contract>('/api/v1/admin/config/contracts', data, ADMIN_CONFIG_SILENT)
      .then((r) => r.data),

  update: (id: number, data: Partial<Contract>) =>
    api
      .patch<Contract>(`/api/v1/admin/config/contracts/${id}`, data, ADMIN_CONFIG_SILENT)
      .then((r) => r.data),

  delete: (id: number) =>
    api
      .delete<void>(`/api/v1/admin/config/contracts/${id}`, ADMIN_CONFIG_SILENT)
      .then((r) => r.data),
}

// ============ Lookups API (extracted: lookupsClient.ts) ============
export const lookupsApi = createLookupsApi(api)

export const settingsApi = {
  list: (category?: string) =>
    api
      .get<{
        items: SystemSetting[]
        total: number
      }>(`/api/v1/admin/config/settings${category ? `?category=${category}` : ''}`)
      .then((r) => r.data),

  get: (key: string) =>
    api.get<SystemSetting>(`/api/v1/admin/config/settings/${key}`).then((r) => r.data),

  update: (key: string, value: string) =>
    api.patch<SystemSetting>(`/api/v1/admin/config/settings/${key}`, { value }).then((r) => r.data),
}

// ============ Vehicle Checklists API (PAMS Integration) ============

export interface VehicleDefect {
  id: number
  pams_table: string
  pams_record_id: number
  check_field: string
  check_value?: string
  priority: string
  status: string
  notes?: string
  vehicle_reg?: string
  created_by_id?: number
  assigned_to_email?: string
  created_at?: string
  updated_at?: string
}

export interface VehicleDefectCreate {
  pams_table: string
  pams_record_id: number
  check_field: string
  check_value?: string
  priority: string
  notes?: string
  vehicle_reg?: string
  assigned_to_email?: string
}

export interface VehicleDefectUpdate {
  priority?: string
  status?: string
  notes?: string
  assigned_to_email?: string
}

export interface DefectActionCreate {
  title: string
  description: string
  due_date?: string
  assigned_to_email?: string
  action_type?: string
}

export interface AnalyticsSummary {
  total_daily_checks: number
  total_monthly_checks: number
  open_defects: number
  p1_defects: number
  p2_defects: number
  p3_defects: number
  overdue_actions: number
  pass_rate_daily?: number
  pass_rate_monthly?: number
  last_sync?: string
}

export interface TrendDataPoint {
  date: string
  p1: number
  p2: number
  p3: number
  total: number
}

export interface HeatmapEntry {
  check_field: string
  failure_count: number
  pams_table: string
}

export const vehicleChecklistsApi = {
  schema: () => api.get('/api/v1/vehicle-checklists/schema'),

  listDaily: (page = 1, pageSize = 25) =>
    api.get<PaginatedResponse<Record<string, unknown>>>(
      `/api/v1/vehicle-checklists/daily?page=${page}&page_size=${pageSize}`,
    ),

  listMonthly: (page = 1, pageSize = 25) =>
    api.get<PaginatedResponse<Record<string, unknown>>>(
      `/api/v1/vehicle-checklists/monthly?page=${page}&page_size=${pageSize}`,
    ),

  getDaily: (id: number) =>
    api.get<Record<string, unknown>>(`/api/v1/vehicle-checklists/daily/${id}`),

  getMonthly: (id: number) =>
    api.get<Record<string, unknown>>(`/api/v1/vehicle-checklists/monthly/${id}`),

  listDefects: (page = 1, pageSize = 25, priority?: string, status?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (priority) params.set('priority', priority)
    if (status) params.set('status', status)
    return api.get<PaginatedResponse<VehicleDefect>>(`/api/v1/vehicle-checklists/defects?${params}`)
  },

  createDefect: (data: VehicleDefectCreate) =>
    api.post<VehicleDefect>('/api/v1/vehicle-checklists/defects', data),

  getDefect: (id: number) => api.get<VehicleDefect>(`/api/v1/vehicle-checklists/defects/${id}`),

  updateDefect: (id: number, data: VehicleDefectUpdate) =>
    api.patch<VehicleDefect>(`/api/v1/vehicle-checklists/defects/${id}`, data),

  createDefectAction: (defectId: number, data: DefectActionCreate) =>
    api.post(`/api/v1/vehicle-checklists/defects/${defectId}/actions`, data),

  triggerSync: () => api.post('/api/v1/vehicle-checklists/sync'),

  analyticsSummary: () => api.get<AnalyticsSummary>('/api/v1/vehicle-checklists/analytics/summary'),

  analyticsTrends: (days = 30) =>
    api.get<TrendDataPoint[]>(`/api/v1/vehicle-checklists/analytics/trends?days=${days}`),

  analyticsHeatmap: (limit = 20) =>
    api.get<HeatmapEntry[]>(`/api/v1/vehicle-checklists/analytics/heatmap?limit=${limit}`),

  exportDailyCsv: () =>
    api.get('/api/v1/vehicle-checklists/analytics/export/daily', { responseType: 'blob' }),

  exportMonthlyCsv: () =>
    api.get('/api/v1/vehicle-checklists/analytics/export/monthly', { responseType: 'blob' }),

  exportDefectsCsv: () =>
    api.get('/api/v1/vehicle-checklists/analytics/export/defects', { responseType: 'blob' }),
}

export interface ExternalAuditImportJob {
  id: number
  reference_number: string
  audit_run_id: number
  source_document_asset_id: number
  status: string
  provider_name?: string | null
  provider_model?: string | null
  source_filename?: string | null
  extraction_method?: string | null
  extraction_text_preview?: string | null
  page_count?: number | null
  source_sheet_count?: number | null
  has_tabular_data: boolean
  analysis_summary?: string | null
  detected_scheme?: string | null
  detected_scheme_confidence?: number | null
  scheme_version?: string | null
  issuer_name?: string | null
  report_date?: string | null
  overall_score?: number | null
  max_score?: number | null
  score_percentage?: number | null
  outcome_status?: string | null
  organization_name?: string | null
  auditor_name?: string | null
  audit_type?: string | null
  certificate_number?: string | null
  audit_scope?: string | null
  next_audit_date?: string | null
  provenance_json?: Record<string, unknown> | null
  classification_basis_json?: Record<string, unknown> | null
  score_breakdown_json?: Array<Record<string, unknown>> | null
  evidence_preview_json?: Array<Record<string, unknown>> | null
  positive_summary_json?: Array<Record<string, unknown>> | null
  nonconformity_summary_json?: Array<Record<string, unknown>> | null
  improvement_summary_json?: Array<Record<string, unknown>> | null
  promotion_summary_json?: Record<string, unknown> | null
  processing_warnings_json?: Array<string | Record<string, unknown>> | null
  specialist_home_path?: string | null
  specialist_home_label?: string | null
  error_code?: string | null
  error_detail?: string | null
  created_at: string
  processed_at?: string | null
  promoted_at?: string | null
  promote_attempt?: number
  promote_lease_expires_at?: string | null
  promote_total?: number | null
  promote_succeeded?: number | null
  promote_failed?: number | null
  promote_progress_json?: Record<string, unknown> | null
}

export interface ExternalAuditImportDraft {
  id: number
  import_job_id: number
  audit_run_id: number
  status: string
  title: string
  description: string
  severity: string
  finding_type: string
  confidence_score?: number | null
  competence_verdict?: string | null
  source_pages_json?: number[] | null
  evidence_snippets_json?: string[] | null
  mapped_frameworks_json?: Array<Record<string, unknown>> | null
  mapped_standards_json?: Array<Record<string, unknown>> | null
  suggested_action_title?: string | null
  suggested_action_description?: string | null
  suggested_risk_title?: string | null
  review_notes?: string | null
  promoted_finding_id?: number | null
  promoted_at?: string | null
  promotion_error_code?: string | null
  provenance_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ExternalAuditPromotionReconciliation {
  job_id: number
  audit_run_id: number
  audit_reference: string
  job_status: string
  canonical_read_model: string
  specialist_home: { path: string; label: string }
  scheme_alignment?: Record<string, unknown> | null
  accepted_total: number
  promoted_total: number
  accepted_pending_total: number
  failed_total: number
  failed_drafts: Array<Record<string, unknown>>
  materialized: {
    audit_findings: number
    capa_actions: number
    enterprise_risks: number
    uvdb_audit_id?: number | null
    external_audit_record_id?: number | null
  }
  proof_matrix: Array<{ step: string; status: string; detail: string }>
  draft_results: Array<Record<string, unknown>>
  view_links: Record<string, string>
}

export const externalAuditImportsApi = {
  createJob: (data: { audit_run_id: number; source_document_asset_id?: number }) =>
    api.post<ExternalAuditImportJob>('/api/v1/external-audit-imports/jobs', data),

  queueJob: (jobId: number) =>
    api.post<ExternalAuditImportJob>(`/api/v1/external-audit-imports/jobs/${jobId}/queue`),

  processJob: (jobId: number) =>
    api.post<ExternalAuditImportJob>(`/api/v1/external-audit-imports/jobs/${jobId}/process`, null, {
      timeout: PROCESSING_TIMEOUT_MS,
    }),

  getLatestJobForRun: (auditRunId: number) =>
    api.get<ExternalAuditImportJob>(`/api/v1/external-audit-imports/runs/${auditRunId}/latest-job`),

  getJob: (jobId: number) =>
    api.get<ExternalAuditImportJob>(`/api/v1/external-audit-imports/jobs/${jobId}`),

  getReconciliation: (jobId: number) =>
    api.get<ExternalAuditPromotionReconciliation>(`/api/v1/external-audit-imports/jobs/${jobId}/reconciliation`),

  listDrafts: (jobId: number) =>
    api.get<ExternalAuditImportDraft[]>(`/api/v1/external-audit-imports/jobs/${jobId}/drafts`),

  reviewDraft: (
    draftId: number,
    data: {
      status: 'accepted' | 'rejected' | 'draft'
      review_notes?: string
      title?: string
      description?: string
      severity?: string
    },
  ) =>
    api.patch<ExternalAuditImportDraft>(`/api/v1/external-audit-imports/drafts/${draftId}`, data),

  bulkReviewJob: (
    jobId: number,
    data: {
      status: 'accepted' | 'rejected' | 'draft'
      review_notes?: string
    },
  ) => api.post<ExternalAuditImportDraft[]>(`/api/v1/external-audit-imports/jobs/${jobId}/bulk-review`, data),

  promoteJob: (jobId: number) =>
    api.post<ExternalAuditImportJob>(`/api/v1/external-audit-imports/jobs/${jobId}/promote`),
}

// ======================== External Audit Records (Cross-Scheme) ========================

export interface ExternalAuditRecordSummary {
  id: number
  tenant_id: number | null
  scheme: string
  scheme_version: string | null
  scheme_label: string | null
  audit_run_id: number | null
  import_job_id: number | null
  issuer_name: string | null
  company_name: string | null
  report_date: string | null
  overall_score: number | null
  max_score: number | null
  score_percentage: number | null
  section_scores: Record<string, unknown> | null
  outcome_status: string | null
  findings_count: number | null
  major_findings: number | null
  minor_findings: number | null
  observations: number | null
  analysis_summary: string | null
  status: string
  // Planet Mark specific fields (populated when scheme="planet_mark" and carbon sync succeeds)
  carbon_reporting_year_id: number | null
  scope_1_co2e: number | null
  scope_2_co2e: number | null
  scope_3_co2e: number | null
}

export interface ExternalAuditRecordListResponse {
  total: number
  records: ExternalAuditRecordSummary[]
}

export interface ExternalAuditRecordDashboardResponse {
  total_records: number
  average_score_percentage: number | null
  total_findings: number
  total_major: number
  total_minor: number
  total_observations: number
}

export const externalAuditRecordsApi = {
  list: (params?: { scheme?: string; status?: string; skip?: number; limit?: number }) =>
    api.get<ExternalAuditRecordListResponse>('/api/v1/external-audit-records', { params }),

  get: (recordId: number) =>
    api.get<ExternalAuditRecordSummary>(`/api/v1/external-audit-records/${recordId}`),

  dashboard: (params?: { scheme?: string }) =>
    api.get<ExternalAuditRecordDashboardResponse>('/api/v1/external-audit-records/dashboard', { params }),
}

// ============ Governed Knowledge Bank API ============

export type {
  KnowledgeEvidenceLink,
  MapEvidenceResponse,
  GenerateQuizOptions,
  QuizDraft,
  DiscussionThread,
  DiscussionMessage,
  RegulatoryImpact,
  ScanStandardResponse,
  AssessEntityResponse,
  RelatedDocumentHit,
  AssessmentTrailItem,
  AssessmentTrailResponse,
} from './knowledgeBankClient'

export const knowledgeBankApi = createKnowledgeBankApi(api)

// ============ Document Campaigns API ============

export type {
  DocumentCampaignAssignment,
  DocumentCampaignAssignmentListResponse,
  DocumentCampaignQuiz,
  DocumentCampaignQuizQuestion,
  DocumentCampaignQuizAnswer,
  DocumentCampaignQuizResult,
  CompleteDocumentCampaignAssignmentRequest,
  SignatureDisposition,
  CampaignAnalyticsFunnel,
  CampaignAnalyticsResponse,
  CampaignComplianceRow,
  ComplianceOverviewResponse,
  ComplianceOverviewSeriesPoint,
  CompliancePeopleQuery,
  CompliancePeopleResponse,
  CompliancePeopleRow,
  CompliancePeopleStatus,
  CampaignRosterQuery,
  ScoreHistogramBucket,
  CampaignRosterResponse,
  CampaignRosterRow,
  CampaignRosterSummary,
  GroupComplianceRow,
  SnoozeAssignmentResponse,
  CampaignAudienceType,
  CampaignGroup,
  CreateCampaignPayload,
  DocumentCampaign,
  LaunchCampaignResponse,
  QuestionInboxThread,
  ReminderDefaults,
  CompliancePassportAssignment,
  CompliancePassportResponse,
  CompliancePassportStats,
} from './documentCampaignClient'

export const documentCampaignApi = createDocumentCampaignApi(api)

// ============ Document Control API ============

export type {
  ControlledDocumentSummary,
  ControlledDocumentListResponse,
  ControlledDocumentDetail,
  ControlledDocumentCreate,
  ControlledDocumentGoldenThread,
} from './documentControlClient'

export const documentControlApi = createDocumentControlApi(api)
// ============ Policy Acknowledgments API ============

export interface PolicyAcknowledgment {
  id: number
  requirement_id: number
  policy_id: number
  user_id: number
  policy_version: string | null
  status: string
  assigned_at: string
  due_date: string
  acknowledged_at: string | null
  first_opened_at: string | null
  time_spent_seconds: number | null
  quiz_score: number | null
  quiz_attempts: number
  quiz_passed: boolean | null
  reminders_sent: number
}

export interface PolicyAcknowledgmentListResponse {
  items: PolicyAcknowledgment[]
  total: number
}

export const policyAcknowledgmentsApi = {
  listMyPending: () =>
    api.get<PolicyAcknowledgmentListResponse>('/api/v1/policy-acknowledgments/my-pending'),
  recordOpen: (acknowledgmentId: number) =>
    api.post(`/api/v1/policy-acknowledgments/${acknowledgmentId}/open`),
  acknowledge: (acknowledgmentId: number, data?: { acceptance_statement?: string }) =>
    api.post<PolicyAcknowledgment>(
      `/api/v1/policy-acknowledgments/${acknowledgmentId}/acknowledge`,
      data ?? {},
    ),
}

export default api
