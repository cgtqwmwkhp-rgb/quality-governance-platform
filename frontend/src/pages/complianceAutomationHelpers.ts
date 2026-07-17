/** Pure helpers for Compliance Automation / Monitoring page — exported for unit tests. */

export function formatStandardCode(code: string): string {
  const labels: Record<string, string> = {
    ISO9001: 'ISO 9001',
    ISO14001: 'ISO 14001',
    ISO45001: 'ISO 45001',
    ISO27001: 'ISO 27001',
  }
  return labels[code] ?? code.replace(/([A-Z]+)(\d+)/, '$1 $2')
}

export function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-success'
  if (score >= 60) return 'bg-info'
  return 'bg-primary'
}
