/**
 * PlantEx Assist (technical: AI Copilot module) is a simulated demo (PX-248).
 *
 * Its replies are hardcoded pattern matches — no inference runs and no tenant
 * data is queried — so it must never appear unless someone has deliberately
 * opted that build in.
 *
 * The gate is the build-time flag VITE_ENABLE_AI_COPILOT_DEMO and nothing else.
 * It fails closed: absent or unrecognised means off, in every environment
 * including production. Baking it truthy for a production build is an explicit
 * decision to show a surface whose banner says the replies are simulated.
 */
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
  return isExplicitCopilotDemoFlagEnabled()
}
