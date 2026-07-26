import { Navigate } from 'react-router-dom'
import { isAIIntelligenceRouteEnabled } from '../config/aiIntelligenceRoute'
import NotFound from './NotFound'

/**
 * AI Intelligence Hub — a legacy alias onto the live Safety Insights Analyst.
 *
 * Gated by `VITE_ENABLE_AI_INTELLIGENCE_ROUTE` (PX-285). App.tsx already omits
 * the route while the flag is off; this guard repeats the check so the alias
 * cannot be reopened by mounting the component directly.
 */
export default function AIIntelligence() {
  if (!isAIIntelligenceRouteEnabled()) {
    return <NotFound />
  }
  return <Navigate to="/analytics/safety-insights" replace />
}
