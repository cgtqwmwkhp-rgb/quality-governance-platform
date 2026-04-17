/**
 * Centralized authentication token utilities.
 *
 * TOKEN CONTRACT:
 * - Admin login stores token in: localStorage['access_token']
 * - Portal login stores token in: sessionStorage['platform_access_token']
 *
 * This module provides a single source of truth for token access.
 */

const ADMIN_TOKEN_KEY = 'access_token'
const ADMIN_REFRESH_TOKEN_KEY = 'refresh_token'
const PORTAL_TOKEN_KEY = 'platform_access_token'
const PORTAL_REFRESH_TOKEN_KEY = 'platform_refresh_token'

/**
 * Get the platform refresh token (portal/SSO only).
 */
export function getPlatformRefreshToken(): string | null {
  return localStorage.getItem(ADMIN_REFRESH_TOKEN_KEY) || sessionStorage.getItem(PORTAL_REFRESH_TOKEN_KEY)
}

/**
 * Get the current platform JWT token.
 * Checks admin storage first (localStorage), then portal storage (sessionStorage).
 *
 * @returns The platform JWT token, or null if not authenticated
 */
export function getPlatformToken(): string | null {
  // Admin tokens are in localStorage
  const adminToken = localStorage.getItem(ADMIN_TOKEN_KEY)
  if (adminToken) {
    return adminToken
  }

  // Portal tokens are in sessionStorage
  const portalToken = sessionStorage.getItem(PORTAL_TOKEN_KEY)
  if (portalToken) {
    return portalToken
  }

  return null
}

/**
 * Check if the user is authenticated (has a valid token stored).
 * Note: This does NOT validate the token - only checks if one exists.
 *
 * @returns true if a token is present
 */
export function hasToken(): boolean {
  return getPlatformToken() !== null
}

/**
 * Clear all authentication tokens (logout).
 */
export function clearTokens(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  localStorage.removeItem(ADMIN_REFRESH_TOKEN_KEY)
  sessionStorage.removeItem(PORTAL_TOKEN_KEY)
  sessionStorage.removeItem(PORTAL_REFRESH_TOKEN_KEY)
}

/**
 * Check if the current session is an admin session (token in localStorage).
 */
export function isAdminSession(): boolean {
  return localStorage.getItem(ADMIN_TOKEN_KEY) !== null
}

/**
 * Set the admin token (used by admin login flow).
 */
export function setAdminToken(token: string, refreshToken?: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token)
  if (refreshToken) {
    localStorage.setItem(ADMIN_REFRESH_TOKEN_KEY, refreshToken)
  }
}

/**
 * Set the portal token (used by portal/SSO login flow).
 */
export function setPortalToken(accessToken: string, refreshToken?: string): void {
  sessionStorage.setItem(PORTAL_TOKEN_KEY, accessToken)
  if (refreshToken) {
    sessionStorage.setItem('platform_refresh_token', refreshToken)
  }
}

/**
 * Decode a JWT token payload (without verification).
 * Used for reading claims like expiration.
 *
 * @param token - The JWT token to decode
 * @returns The decoded payload, or null if invalid
 */
export function decodeTokenPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) {
      return null
    }
    const payload = parts[1]
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

/**
 * Clock-skew buffer for token expiry comparisons.
 *
 * Treat a token as expired when the device clock is within this many
 * seconds of the JWT `exp`. We're generous (120s) because tablets in the
 * field frequently have drifted system clocks, and a wrong-but-recoverable
 * "needs refresh" decision is far cheaper than a hard logout.
 */
export const TOKEN_SKEW_SECONDS = 120

/**
 * Schedule a proactive refresh this many seconds before `exp`.
 * Used by the session-keepalive hook to keep long audit sessions warm.
 */
export const TOKEN_REFRESH_LEAD_SECONDS = 300

/**
 * Read the JWT `exp` claim (unix seconds) or null if absent/invalid.
 */
export function getTokenExpirySeconds(token: string): number | null {
  const payload = decodeTokenPayload(token)
  if (!payload || typeof payload.exp !== 'number') {
    return null
  }
  return payload.exp
}

/**
 * Check if a token is expired.
 *
 * Uses TOKEN_SKEW_SECONDS as a buffer so we treat a token as expired
 * slightly before its true `exp`. This protects against device clock drift
 * common on tablets in the field.
 *
 * @param token - The JWT token to check
 * @returns true if expired or invalid, false if still valid
 */
export function isTokenExpired(token: string): boolean {
  const exp = getTokenExpirySeconds(token)
  if (exp === null) {
    return true
  }
  const now = Math.floor(Date.now() / 1000)
  return exp < now - TOKEN_SKEW_SECONDS
}

/**
 * Check whether a token is expired OR within the proactive-refresh window.
 * Used to decide if we should silently refresh before letting a request go out
 * or before letting the user resume an audit after a long pause.
 */
export function shouldRefreshToken(token: string): boolean {
  const exp = getTokenExpirySeconds(token)
  if (exp === null) {
    return true
  }
  const now = Math.floor(Date.now() / 1000)
  return exp - now <= TOKEN_REFRESH_LEAD_SECONDS
}

/**
 * Get a valid (non-expired) platform token.
 * Returns null if no token or token is expired.
 *
 * @returns Valid token or null
 */
export function getValidPlatformToken(): string | null {
  const token = getPlatformToken()
  if (!token) {
    return null
  }
  if (isTokenExpired(token)) {
    return null
  }
  return token
}

function normalizeRoleClaims(payload: Record<string, unknown> | null): string[] {
  if (!payload) return []

  const rawRole = payload.role
  const rawRoles = payload.roles
  const candidates: unknown[] = []

  if (typeof rawRole === 'string') {
    candidates.push(rawRole)
  }
  if (typeof rawRoles === 'string') {
    candidates.push(...rawRoles.split(','))
  } else if (Array.isArray(rawRoles)) {
    candidates.push(...rawRoles)
  }

  return candidates
    .filter((value): value is string => typeof value === 'string')
    .map((value) => value.trim())
    .filter(Boolean)
}

export function getUserRoles(): string[] {
  const token = getPlatformToken()
  if (!token) return ['viewer']

  const payload = decodeTokenPayload(token)
  const roles = normalizeRoleClaims(payload)
  return roles.length > 0 ? roles : ['viewer']
}

/**
 * Extract the user's role from the JWT token.
 * Falls back to 'viewer' if no role claim is present.
 */
export function getUserRole(): string {
  return getUserRoles()[0] || 'viewer'
}

/**
 * Check if the current user has one of the allowed roles.
 */
export function hasRole(...allowedRoles: string[]): boolean {
  const roles = getUserRoles().map((role) => role.toLowerCase())
  return allowedRoles.some((allowedRole) => roles.includes(allowedRole.toLowerCase()))
}

export function isSuperuser(): boolean {
  const token = getPlatformToken()
  if (!token) return false
  const payload = decodeTokenPayload(token)
  return payload?.is_superuser === true
}
