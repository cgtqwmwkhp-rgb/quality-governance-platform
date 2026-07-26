export type DistributionRow = {
  module: string
  distributionTotal: number | null
}

/** Rows eligible for the period-scoped module distribution chart (PX-195). */
export function rowsForPeriodDistribution<T extends DistributionRow>(rows: T[]): T[] {
  return rows.filter((row) => row.distributionTotal != null && row.distributionTotal >= 0)
}

export function periodDistributionDenominator(rows: DistributionRow[]): number | null {
  const values = rows
    .map((row) => row.distributionTotal)
    .filter((value): value is number => value != null)
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0)
}

export function periodDistributionPercent(
  rowTotal: number | null,
  denominator: number | null,
): number {
  if (rowTotal == null || denominator == null || denominator <= 0) return 0
  return (rowTotal / denominator) * 100
}
