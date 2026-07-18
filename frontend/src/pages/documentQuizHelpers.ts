export function sanitizeQuestionCount(raw: string): number {
  const digits = raw.replace(/\D/g, '')
  if (!digits) return 1
  const parsed = parseInt(digits, 10)
  return Math.min(30, Math.max(1, parsed))
}

export function normalizeQuestionCountInput(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (!digits) return ''
  return String(sanitizeQuestionCount(digits))
}

export function isQuizAiFallback(questions: unknown[], requestedCount: number): boolean {
  if (!Array.isArray(questions) || questions.length === 0) return true
  if (questions.length > 1 && questions.length >= requestedCount) return false

  const first = questions[0] as { explanation?: string; question?: string } | undefined
  const explanation = String(first?.explanation ?? '')
  if (/fallback|ai unavailable|ai failed/i.test(explanation)) return true

  return questions.length === 1 && questions.length < requestedCount
}
