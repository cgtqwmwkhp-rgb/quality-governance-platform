import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * CAPA / Actions tab parity across Incident, Near Miss, RTA, Complaint.
 * Mocks APIs; asserts Actions tab + Open CAPA / Add Action header pattern (RTA gold standard).
 */

const E2E_JWT =
  'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e'

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

const ACTION = {
  id: 77,
  title: 'Fit winch guard',
  status: 'open',
  priority: 'high',
  due_date: '2026-08-01',
  source_type: 'incident',
  source_id: 11,
}

async function installMocks(page: Page) {
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('token', token)
  }, E2E_JWT)

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    if (path.includes('/auth/me') && method === 'GET') {
      await json(route, {
        id: 1,
        email: 'e2e@example.com',
        full_name: 'E2E Admin',
        role: 'admin',
        is_superuser: true,
        tenant_id: 1,
      })
      return
    }

    if (path.match(/\/incidents\/\d+$/) && method === 'GET') {
      await json(route, {
        id: 11,
        reference_number: 'INC-11',
        title: 'Loader slip',
        description: 'Slip',
        incident_type: 'injury',
        severity: 'high',
        status: 'reported',
        incident_date: '2026-07-01T10:00:00Z',
        reported_date: '2026-07-01T10:00:00Z',
        created_at: '2026-07-01T10:00:00Z',
        updated_at: '2026-07-01T10:00:00Z',
        location: 'Yard',
        department: 'Facilities',
      })
      return
    }

    if (path.match(/\/near-misses\/\d+$/) && method === 'GET') {
      await json(route, {
        id: 5,
        reference_number: 'NM-5',
        description: 'Near miss',
        contract: 'Facilities',
        location: 'Yard',
        event_date: '2026-07-01T10:00:00Z',
        status: 'open',
        priority: 'medium',
        reporter_name: 'Alex',
        potential_severity: 'high',
        is_hipo: false,
      })
      return
    }

    if (path.match(/\/rtas\/\d+$/) && method === 'GET') {
      await json(route, {
        id: 42,
        reference_number: 'RTA-42',
        title: 'Fleet collision',
        severity: 'medium',
        status: 'reported',
        reported_date: '2026-07-01T10:00:00Z',
        created_at: '2026-07-01T10:00:00Z',
      })
      return
    }

    if (path.match(/\/complaints\/\d+$/) && method === 'GET') {
      await json(route, {
        id: 9,
        reference_number: 'CMP-9',
        title: 'Service delay',
        description: 'Late attendance',
        complaint_type: 'service',
        status: 'open',
        received_date: '2026-07-01T10:00:00Z',
        created_at: '2026-07-01T10:00:00Z',
        complainant_name: 'Pat Customer',
      })
      return
    }

    if ((path.includes('/actions') || path.endsWith('/actions/')) && method === 'GET') {
      const sourceType = url.searchParams.get('source_type') || 'incident'
      await json(route, {
        items: [
          {
            ...ACTION,
            source_type: sourceType,
            display_status: 'open',
          },
        ],
        total: 1,
      })
      return
    }

    if (path.includes('/running-sheet')) {
      await json(route, [])
      return
    }

    if (path.includes('/investigations')) {
      await json(route, { items: [], total: 0 })
      return
    }

    await json(route, { items: [], total: 0 })
  })
}

test.describe('CAPA case tab parity', () => {
  test('incident has Actions tab and Open CAPA header', async ({ page }) => {
    await installMocks(page)
    await page.goto('/incidents/11')
    await expect(page.getByRole('heading', { name: /Loader slip/i })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('incident-actions-tab')).toBeVisible()
    await expect(page.getByTestId('incident-open-capa')).toBeVisible()
    await page.getByTestId('incident-actions-tab').click()
    await expect(page.getByTestId('incident-capa-actions-panel')).toBeVisible()
    await expect(page.getByText('Fit winch guard')).toBeVisible()
  })

  test('near miss has Actions tab and Open CAPA header', async ({ page }) => {
    await installMocks(page)
    await page.goto('/near-misses/5')
    await expect(page.getByRole('heading', { name: /NM-5/i })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('near-miss-actions-tab')).toBeVisible()
    await expect(page.getByTestId('near-miss-open-capa')).toBeVisible()
    await page.getByTestId('near-miss-actions-tab').click()
    await expect(page.getByTestId('near-miss-capa-actions-panel')).toBeVisible()
  })

  test('rta Actions tab uses shared CAPA panel', async ({ page }) => {
    await installMocks(page)
    await page.goto('/rtas/42')
    await expect(page.getByRole('heading', { name: /Fleet collision/i })).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByTestId('rta-open-capa')).toBeVisible()
    await page.getByRole('tab', { name: /Actions/i }).click()
    await expect(page.getByTestId('rta-capa-actions-panel')).toBeVisible()
  })

  test('complaint has Actions tab and Open CAPA header', async ({ page }) => {
    await installMocks(page)
    await page.goto('/complaints/9')
    await expect(page.getByText(/CMP-9|Service delay/i).first()).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('complaint-actions-tab')).toBeVisible()
    await expect(page.getByTestId('complaint-open-capa')).toBeVisible()
    await page.getByTestId('complaint-actions-tab').click()
    await expect(page.getByTestId('complaint-capa-actions-panel')).toBeVisible()
  })
})
