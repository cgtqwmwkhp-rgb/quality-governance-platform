/**
 * `/ai-intelligence` is a legacy alias that lands on the Safety Insights Analyst (PX-285).
 *
 * The Analyst sends real case narratives to third-party processors (Gemini,
 * Claude, Perplexity). The alias is a second, separately-labelled way into that
 * processing which no longer carries its own screen, so it must stay closed
 * until the alias itself is signed off.
 *
 * Closing this alias does not close the Analyst: `/analytics/safety-insights`
 * is a first-class route with its own sidebar entry and is unaffected here.
 *
 * Both conditions are required (fail closed):
 * 1. Detected environment is not production
 * 2. Explicit build-time flag VITE_ENABLE_AI_INTELLIGENCE_ROUTE is truthy
 */
import { detectEnvironment } from './apiBase'

function isExplicitAIIntelligenceRouteFlagEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_AI_INTELLIGENCE_ROUTE
  if (typeof flag === 'boolean') {
    return flag
  }
  if (typeof flag !== 'string') {
    return false
  }
  const normalized = flag.trim().toLowerCase()
  return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

export function isAIIntelligenceRouteEnabled(): boolean {
  if (detectEnvironment() === 'production') {
    return false
  }
  return isExplicitAIIntelligenceRouteFlagEnabled()
}
