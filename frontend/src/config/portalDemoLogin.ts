/**
 * Portal demo login is a non-production convenience only.
 *
 * Both conditions are required (fail closed):
 * 1. Detected environment is not production
 * 2. Explicit build-time flag VITE_ENABLE_PORTAL_DEMO_LOGIN is truthy
 */
import { detectEnvironment } from './apiBase'

function isExplicitDemoFlagEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_PORTAL_DEMO_LOGIN
  if (typeof flag === 'boolean') {
    return flag
  }
  if (typeof flag !== 'string') {
    return false
  }
  const normalized = flag.trim().toLowerCase()
  return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

export function isPortalDemoLoginEnabled(): boolean {
  if (detectEnvironment() === 'production') {
    return false
  }
  return isExplicitDemoFlagEnabled()
}
