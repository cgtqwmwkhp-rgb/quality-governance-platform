import { expect, test, type Route } from '@playwright/test'

const RUN_REQUIREMENTS_ADMIN_E2E = process.env.WF1_REQUIREMENTS_ADMIN_E2E === 'true'

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

test.describe('CUJ-01 supervisor reviews competency requirements', () => {
  test.skip(
    !RUN_REQUIREMENTS_ADMIN_E2E,
    'WF1_REQUIREMENTS_ADMIN_E2E=true requires the workforce requirements-admin route and supervisor fixture.',
  )

  test('shows configured requirements without concealing API failures', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'supervisor-e2e-token')
    })
    await page.route('**/api/v1/competency-requirements/**', async (route) => {
      await json(route, {
        items: [
          {
            id: 3,
            asset_type_id: 2,
            template_id: 5,
            name: 'MEWP competence',
            is_mandatory: true,
            reassessment_interval_days: 365,
            site: 'Cardiff',
            tenant_id: 1,
            created_at: '2026-07-15T00:00:00Z',
            updated_at: '2026-07-15T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      })
    })

    await page.goto('/workforce/requirements', { waitUntil: 'domcontentloaded' })

    await expect(page.getByTestId('requirements-admin')).toBeVisible()
    await expect(page.getByTestId('requirements-admin-table')).toContainText('MEWP competence')
    await expect(page.getByTestId('requirements-admin-next-step')).toBeVisible()
  })
})
