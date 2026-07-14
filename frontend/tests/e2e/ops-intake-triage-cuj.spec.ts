import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * CUJ-OPS-INTAKE-TRIAGE — unassigned tabs + SMTP honesty (mocked APIs).
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

const sampleIncident = {
  id: 11,
  reference_number: 'INC-TRIAGE-001',
  title: 'Unassigned portal incident',
  description: 'Needs triage',
  incident_type: 'injury',
  severity: 'medium',
  status: 'reported',
  incident_date: '2026-07-13T10:00:00Z',
  reported_date: '2026-07-13T10:00:00Z',
  created_at: '2026-07-13T10:00:00Z',
  owner_id: null,
}

const sampleComplaint = {
  id: 21,
  reference_number: 'COMP-TRIAGE-001',
  title: 'Unassigned portal complaint',
  description: 'Needs triage',
  complaint_type: 'service',
  priority: 'medium',
  status: 'received',
  received_date: '2026-07-13T10:00:00Z',
  complainant_name: 'Portal User',
  created_at: '2026-07-13T10:00:00Z',
  owner_id: null,
}

async function installTriageMocks(page: Page, options?: { emailConfigured?: boolean }) {
  const seen = { incidentUnassigned: false, complaintUnassigned: false }

  await page.route('**/readyz**', async (route) => {
    await json(route, { email_configured: options?.emailConfigured ?? false })
  })

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    if (path.includes('/notifications') && path.includes('delivery')) {
      await json(route, { email_configured: options?.emailConfigured ?? false })
      return
    }

    if (path.match(/\/incidents\/?$/) && method === 'GET') {
      const owner = url.searchParams.get('owner')
      if (owner === 'unassigned') {
        seen.incidentUnassigned = true
        await json(route, {
          items: [sampleIncident],
          total: 1,
          page: 1,
          page_size: 50,
          pages: 1,
        })
        return
      }
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 1 })
      return
    }

    if (path.match(/\/complaints\/?$/) && method === 'GET') {
      const owner = url.searchParams.get('owner')
      if (owner === 'unassigned') {
        seen.complaintUnassigned = true
        await json(route, {
          items: [sampleComplaint],
          total: 1,
          page: 1,
          page_size: 50,
          pages: 1,
        })
        return
      }
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 1 })
      return
    }

    if (path.includes('/users/search') && method === 'GET') {
      await json(route, [{ id: 42, email: 'owner@example.com', full_name: 'Case Owner' }])
      return
    }

    if (path.match(/\/incidents\/\d+$/) && method === 'PATCH') {
      await json(route, { ...sampleIncident, owner_id: 42 })
      return
    }

    if (path.match(/\/complaints\/\d+$/) && method === 'PATCH') {
      await json(route, { ...sampleComplaint, owner_id: 42 })
      return
    }

    await json(route, {})
  })

  return seen
}

test.describe('CUJ ops intake triage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((token) => {
      window.localStorage.setItem('access_token', token)
      window.localStorage.setItem('token', token)
    }, E2E_JWT)
  })

  test('Incidents unassigned tab uses server owner=unassigned and shows SMTP honesty', async ({
    page,
  }) => {
    const seen = await installTriageMocks(page, { emailConfigured: false })
    await page.goto('/incidents')
    await page.getByTestId('incidents-filter-unassigned').click()
    await expect(page.getByTestId('incidents-server-filter-label')).toBeVisible()
    await expect(page.getByTestId('incidents-email-unavailable')).toBeVisible()
    await expect(page.getByText('INC-TRIAGE-001')).toBeVisible()
    expect(seen.incidentUnassigned).toBe(true)
  })

  test('Complaints unassigned tab uses server owner=unassigned', async ({ page }) => {
    const seen = await installTriageMocks(page, { emailConfigured: false })
    await page.goto('/complaints?owner=unassigned')
    await expect(page.getByTestId('complaints-server-filter-label')).toBeVisible()
    await expect(page.getByTestId('complaints-email-unavailable')).toBeVisible()
    await expect(page.getByText('COMP-TRIAGE-001')).toBeVisible()
    expect(seen.complaintUnassigned).toBe(true)
  })
})
