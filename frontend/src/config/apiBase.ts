/**
 * Centralized API Base URL configuration.
 * Single source of truth for all API calls.
 * 
 * SECURITY: Enforces HTTPS in production to prevent mixed content errors.
 * ENVIRONMENT ISOLATION: Uses build-time VITE_API_URL, with hostname fallback for dev.
 * 
 * Priority:
 * 1. VITE_API_URL (build-time env var) - MUST be set correctly in CI
 * 2. Hostname detection (for local development only)
 */

// API URLs for each environment
const API_URLS = {
  staging: 'https://qgp-staging.ashymushroom-85447e68.uksouth.azurecontainerapps.io',
  production: 'https://app-qgp-prod.azurewebsites.net',
  development: 'http://localhost:8000',
} as const;

export type Environment = 'staging' | 'production' | 'development';

/**
 * Detect the current environment based on build-time configuration.
 * 
 * Priority:
 * 1. VITE_ENVIRONMENT explicit setting
 * 2. Infer from VITE_API_URL if set
 * 3. Vite's DEV mode for local development
 * 4. Default to production (safe fallback)
 */
export function detectEnvironment(): Environment {
  // Explicit environment override
  const explicitEnv = import.meta.env['VITE_ENVIRONMENT'];
  if (explicitEnv && ['staging', 'production', 'development'].includes(explicitEnv)) {
    return explicitEnv as Environment;
  }
  
  // Infer from API URL (build-time)
  const apiUrl = import.meta.env.VITE_API_URL;
  if (apiUrl) {
    if (apiUrl.includes('staging') || apiUrl.includes('localhost')) {
      return 'staging';
    }
    if (apiUrl.includes('prod')) {
      return 'production';
    }
  }
  
  // Vite development mode
  if (import.meta.env.DEV) {
    return 'development';
  }
  
  // Safe default for production builds without explicit config
  return 'production';
}

/**
 * Get the API base URL based on the detected environment.
 * 
 * Priority:
 * 1. VITE_API_URL environment variable (build-time override)
 * 2. Hostname-based environment detection
 */
export function getApiBaseUrl(): string {
  // Build-time override takes precedence
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.trim()) {
    let baseUrl = envUrl.trim();
    
    // Enforce HTTPS (except localhost)
    if (baseUrl.startsWith('http://') && !baseUrl.includes('localhost')) {
      baseUrl = baseUrl.replace('http://', 'https://');
      console.warn('[API Config] Converted HTTP to HTTPS for security');
    }
    
    // Remove trailing slash
    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.slice(0, -1);
    }
    
    return baseUrl;
  }
  
  // Use hostname-based detection
  const env = detectEnvironment();
  return API_URLS[env];
}

/**
 * Get the expected environment for the current frontend.
 */
export function getExpectedEnvironment(): Environment {
  return detectEnvironment();
}

/**
 * Validate that the API environment matches the frontend environment.
 * Returns null if matched, or an error message if mismatched.
 */
export async function validateEnvironmentMatch(): Promise<string | null> {
  const expectedEnv = getExpectedEnvironment();
  
  // Skip validation in development
  if (expectedEnv === 'development') {
    return null;
  }
  
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/meta/version`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    
    if (!response.ok) {
      console.warn('[API Config] Failed to fetch API version for environment validation');
      return null; // Don't block on validation failures
    }
    
    const data = await response.json();
    const apiEnv = data.environment?.toLowerCase();
    
    if (apiEnv && apiEnv !== expectedEnv) {
      return `Environment mismatch: Frontend expects ${expectedEnv}, but API reports ${apiEnv}`;
    }
    
    return null; // Matched
  } catch (error) {
    console.warn('[API Config] Environment validation failed:', error);
    return null; // Don't block on network errors
  }
}

/**
 * Log the API configuration at module load time.
 */
function logApiConfig(): void {
  const env = detectEnvironment();
  const url = getApiBaseUrl();
  
  console.log(`[API Config] Environment: ${env}`);
  console.log(`[API Config] Base URL: ${url}`);
  
  // Warn if build-time URL doesn't match detected environment
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) {
    if (env === 'staging' && envUrl.includes('prod')) {
      console.error('[API Config] WARNING: Staging frontend configured with production API URL!');
    } else if (env === 'production' && envUrl.includes('staging')) {
      console.error('[API Config] WARNING: Production frontend configured with staging API URL!');
    }
  }
}

// Run on module load
logApiConfig();

export const API_BASE_URL = getApiBaseUrl();
export const CURRENT_ENVIRONMENT = detectEnvironment();
