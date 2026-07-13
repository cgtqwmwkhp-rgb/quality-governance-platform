import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * Actions My Work / Overdue — server-side filter CUJ (mocked APIs).
 */

const E2E_JWT =
  'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiI0MiIsImV4cCI6MTgxNTE4ODE1NSwicm9sZSI6ImFkbWluIiwiaXNfc3VwZXJ1c2VyIjp0cnVlLCJ0ZW5hbnRfaWQiOjF9.e2e'

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

const sampleAction = {
  id: 1,
  reference_number: 'ACT-0001',
  title: 'Fix overdue CAPA',
  description: 'Close the loop',
  action_type: 'corrective',
  priority: 'high',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:1',
  source_type: 'audit_finding',
  source_id: 9,
  owner_id: 42,
  due_date: '2020-01-01',
  created_at: '2026-07-01T10:00:00Z',
}

async function installActionsMocks(page: Page, options?: { failOverdue?: boolean }) {
  const seen: { my?: boolean; overdue?: boolean } = {}

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    if (path.includes('/notifications/') && path.includes('delivery')) {
      await json(route, { email_configured: true })
      return
    }

    if (path.endsWith('/actions/summary') && method === 'GET') {
      await json(route, { total: 1, by_display_status: { open: 1, overdue: 1 } })
      return
    }

    if (path.match(/\/actions\/?$/) && method === 'GET') {
      const assignedTo = url.searchParams.get('assigned_to')
      const overdue = url.searchParams.get('overdue')
      if (assignedTo === 'me') seen.my = true
      if (overdue === 'true') {
        seen.overdue = true
        if (options?.failOverdue) {
          await json(route, { detail: 'filter failed' }, 500)
          return
        }
      }
      await json(route, {
        items: [sampleAction],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      })
      return
    }

    await json(route, {})
  })

  return seen
}

test.describe('Actions My Work / Overdue CUJ', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((token) => {
      window.localStorage.setItem('platform_token', token)
      window.localStorage.setItem('access_token', token)
    }, E2E_JWT)
  })

  test('My actions sends assigned_to=me and shows server filter label', async ({ page }) => {
    const seen = await installActionsMocks(page)
    await page.goto('/actions')
    await expect(page.getByTestId('actions-view-mode')).toBeVisible()
    await page.getByTestId('actions-view-my').click()
    await expect(page.getByTestId('actions-server-filter-label')).toContainText('assigned_to=me')
    await expect.poll(() => seen.my === true).toBeTruthy()
  })

  test('Overdue sends overdue=true and surfaces failure toast/label', async ({ page }) => {
    const seen = await installActionsMocks(page, { failOverdue: true })
    await page.goto('/actions')
    await page.getByTestId('actions-view-overdue').click()
    await expect.poll(() => seen.overdue === true).toBeTruthy()
    await expect(page.getByTestId('actions-filter-error').or(page.getByText(/Server filter failed/i))).toBeVisible({
      timeout: 10000,
    })
  })
})
