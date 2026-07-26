/**
 * AI Copilot is a simulated demo, not a production capability (PX-248).
 *
 * Its replies are hardcoded pattern matches — no inference runs and no tenant
 * data is queried — so it must never appear unless someone has deliberately
 * opted a non-production build in.
 *
 * Both conditions are required (fail closed):
 * 1. Detected environment is not production
 * 2. Explicit build-time flag VITE_ENABLE_AI_COPILOT_DEMO is truthy
 */
import { detectEnvironment } from './apiBase'

function isExplicitCopilotDemoFlagEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_AI_COPILOT_DEMO
  if (typeof flag === 'boolean') {
    return flag
  }
  if (typeof flag !== 'string') {
    return false
  }
  const normalized = flag.trim().toLowerCase()
  return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

export function isAICopilotDemoEnabled(): boolean {
  if (detectEnvironment() === 'production') {
    return false
  }
  return isExplicitCopilotDemoFlagEnabled()
}
