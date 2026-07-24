import { Navigate } from 'react-router-dom'

/**
 * AI Intelligence Hub — lands on the live Safety Insights Analyst.
 * Legacy /ai-intelligence deep links remain valid.
 */
export default function AIIntelligence() {
  return <Navigate to="/analytics/safety-insights" replace />
}
