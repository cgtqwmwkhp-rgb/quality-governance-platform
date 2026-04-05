/**
 * Risk-register URL segments aligned with FastAPI `src/api/routes/risk_register.py`
 * and `docs/contracts/openapi.json` (bowtie + KRI value).
 */
export function riskRegisterBowtieElementsPath(riskId: number): string {
  return `/api/v1/risk-register/${riskId}/bowtie/elements`
}

export function riskRegisterBowtieElementPath(riskId: number, elementId: number): string {
  return `/api/v1/risk-register/${riskId}/bowtie/elements/${elementId}`
}

export function riskRegisterKriValuePath(kriId: number): string {
  return `/api/v1/risk-register/kris/${kriId}/value`
}
