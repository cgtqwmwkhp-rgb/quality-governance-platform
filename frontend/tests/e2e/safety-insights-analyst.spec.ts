import { test, expect } from '@playwright/test'

test.describe('Safety Insights Analyst CUJ', () => {
  test('runs deep analysis against mocked API and shows micro-theme citations', async ({ page }) => {
    await page.route('**/api/v1/safety-insights/runs**', async (route) => {
      const req = route.request()
      if (req.method() === 'GET' && !req.url().match(/\/runs\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], total: 0 }),
        })
        return
      }
      if (req.method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 42,
            status: 'succeeded',
            progress_pct: 100,
            progress_message: 'Complete',
            scope: 'org',
            modules: ['rta'],
            min_cluster_size: 2,
            include_synthesis: true,
            include_benchmark: false,
            synthesis_available: false,
            research_available: false,
            ratios: {
              corpus: {
                incidents: 4,
                near_misses: 12,
                near_miss_to_incident_ratio: 3,
              },
            },
            micro_themes: [
              {
                id: 1,
                label: 'reversing into stationary object',
                case_count: 3,
                share: 20,
                velocity: 'emerging',
                rationale: 'Three RTAs share reversing narrative',
                case_refs: [
                  { module: 'rta', id: 12, reference_number: 'RTA-12' },
                  { module: 'rta', id: 19, reference_number: 'RTA-19' },
                  { module: 'rta', id: 41, reference_number: 'RTA-41' },
                ],
              },
            ],
            dimensions: [
              {
                id: 1,
                dimension_type: 'location',
                dimension_key: 'Depot A',
                case_count: 2,
                case_refs: [
                  { module: 'rta', id: 12, reference_number: 'RTA-12' },
                  { module: 'rta', id: 19, reference_number: 'RTA-19' },
                ],
              },
            ],
            quality_scorecard: { total: 15, fields: {} },
          }),
        })
        return
      }
      await route.continue()
    })

    await page.goto('/analytics/safety-insights')
    await expect(page.getByRole('heading', { name: /Safety Insights Analyst/i })).toBeVisible()
    await page.getByRole('button', { name: /Run deep analysis/i }).click()
    await expect(page.getByText('reversing into stationary object')).toBeVisible()
    await expect(page.getByRole('link', { name: 'RTA-12' })).toBeVisible()
    await expect(page.getByText('NM : Incident')).toBeVisible()
  })
})
