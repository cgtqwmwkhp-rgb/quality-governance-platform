/**
 * Centralized API Base URL configuration.
 * Single source of truth for all API calls.
 * 
 * SECURITY: Enforces HTTPS in production to prevent mixed content errors.
 */

const DEFAULT_API_URL = 'https://app-qgp-prod.azurewebsites.net';

/**
 * Get the API base URL with HTTPS enforcement.
 * @returns The API base URL, guaranteed to use HTTPS in production.
 */
export function getApiBaseUrl(): string {
  let baseUrl = import.meta.env.VITE_API_URL || DEFAULT_API_URL;
  
  // Trim whitespace
  baseUrl = baseUrl.trim();
  
  // Enforce HTTPS - never allow HTTP in production
  if (baseUrl.startsWith('http://')) {
    baseUrl = baseUrl.replace('http://', 'https://');
    console.warn('[API Config] Converted HTTP to HTTPS for security');
  }
  
  // Handle missing protocol (rare edge case)
  if (!baseUrl.startsWith('https://') && !baseUrl.startsWith('http://')) {
    baseUrl = `https://${baseUrl}`;
  }
  
  // Remove trailing slash for consistency
  if (baseUrl.endsWith('/')) {
    baseUrl = baseUrl.slice(0, -1);
  }
  
  return baseUrl;
}

/**
 * Validate API base URL at module load time.
 * Throws in development if misconfigured.
 */
function validateApiConfig(): void {
  const url = getApiBaseUrl();
  
  // In production, log the configured API URL for debugging
  if (import.meta.env.PROD) {
    console.log('[API Config] Base URL:', url);
  }
  
  // Fail-fast validation in development
  if (import.meta.env.DEV && url.startsWith('http://')) {
    console.error('[API Config] WARNING: Using HTTP in development. This will fail in production.');
  }
}

// Run validation on module load
validateApiConfig();

export const API_BASE_URL = getApiBaseUrl();
