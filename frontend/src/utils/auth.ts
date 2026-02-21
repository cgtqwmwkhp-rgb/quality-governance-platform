/**
 * Centralized authentication token utilities.
 *
 * TOKEN CONTRACT:
 * - Admin login stores token in: localStorage['access_token']
 * - Portal login stores token in: sessionStorage['platform_access_token']
 *
 * This module provides a single source of truth for token access.
 */

const ADMIN_TOKEN_KEY = "access_token";
const PORTAL_TOKEN_KEY = "platform_access_token";

/**
 * Get the current platform JWT token.
 * Checks admin storage first (localStorage), then portal storage (sessionStorage).
 *
 * @returns The platform JWT token, or null if not authenticated
 */
export function getPlatformToken(): string | null {
  // Admin tokens are in localStorage
  const adminToken = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (adminToken) {
    return adminToken;
  }

  // Portal tokens are in sessionStorage
  const portalToken = sessionStorage.getItem(PORTAL_TOKEN_KEY);
  if (portalToken) {
    return portalToken;
  }

  return null;
}

/**
 * Check if the user is authenticated (has a valid token stored).
 * Note: This does NOT validate the token - only checks if one exists.
 *
 * @returns true if a token is present
 */
export function hasToken(): boolean {
  return getPlatformToken() !== null;
}

/**
 * Clear all authentication tokens (logout).
 */
export function clearTokens(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  sessionStorage.removeItem(PORTAL_TOKEN_KEY);
  sessionStorage.removeItem("platform_refresh_token");
}

/**
 * Set the admin token (used by admin login flow).
 */
export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

/**
 * Set the portal token (used by portal/SSO login flow).
 */
export function setPortalToken(
  accessToken: string,
  refreshToken?: string,
): void {
  sessionStorage.setItem(PORTAL_TOKEN_KEY, accessToken);
  if (refreshToken) {
    sessionStorage.setItem("platform_refresh_token", refreshToken);
  }
}

/**
 * Decode a JWT token payload (without verification).
 * Used for reading claims like expiration.
 *
 * @param token - The JWT token to decode
 * @returns The decoded payload, or null if invalid
 */
export function decodeTokenPayload(
  token: string,
): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      return null;
    }
    const payload = parts[1]!;
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Check if a token is expired.
 *
 * @param token - The JWT token to check
 * @returns true if expired or invalid, false if still valid
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeTokenPayload(token);
  if (!payload || typeof payload["exp"] !== "number") {
    return true;
  }
  const now = Math.floor(Date.now() / 1000);
  return payload["exp"] < now - 30;
}

/**
 * Get a valid (non-expired) platform token.
 * Returns null if no token or token is expired.
 *
 * @returns Valid token or null
 */
export function getValidPlatformToken(): string | null {
  const token = getPlatformToken();
  if (!token) {
    return null;
  }
  if (isTokenExpired(token)) {
    return null;
  }
  return token;
}
