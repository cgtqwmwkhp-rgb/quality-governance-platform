import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * CUJ-P10 Portal Field Work Inbox — mocked APIs.
 */

const E2E_JWT =
  'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiI0MiIsImV4cCI6MTgxNTE4ODE1NSwicm9sZSI6ImVuZ2luZWVyIiwiaXNfc3VwZXJ1c2VyIjpmYWxzZSwidGVuYW50X2lkIjoxfQ.e2e'

const portalUser = {
  id: '42',
  email: 'field@example.com',
  name: 'Field Engineer',
  firstName: 'Field',
  lastName: 'Engineer',
}

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

async function installPortalWorkMocks(
  page: Page,
  options?: { unlinked?: boolean; emptyActions?: boolean },
) {
  const seen: { assignedToMe?: boolean; byUserMe?: boolean } = {}

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    if (path.match(/\/actions\/?$/) && method === 'GET') {
      if (url.searchParams.get('assigned_to') === 'me') seen.assignedToMe = true
      await json(route, {
        items: options?.emptyActions ? [] : [sampleAction],
        total: options?.emptyActions ? 0 : 1,
        page: 1,
        page_size: 20,
        pages: options?.emptyActions ? 0 : 1,
      })
      return
    }

    if (path.includes('/policy-acknowledgments/my-pending') && method === 'GET') {
      await json(route, { items: [], total: 0 })
      return
    }

    if (path.includes('/engineers/by-user/me') && method === 'GET') {
      seen.byUserMe = true
      if (options?.unlinked) {
        await json(route, { detail: 'Engineer profile not linked to this user' }, 404)
        return
      }
      await json(route, {
        id: 10,
        external_id: 'eng-1',
        user_id: 42,
        employee_number: 'E-42',
        job_title: 'Field Engineer',
        department: 'Ops',
        site: 'North',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      })
      return
    }

    await json(route, {})
  })

  return seen
}

async function seedPortalSession(page: Page) {
  await page.addInitScript(
    ({ token, user }) => {
      window.sessionStorage.setItem('platform_access_token', token)
      window.localStorage.setItem('portal_user', JSON.stringify(user))
      window.localStorage.setItem('portal_session_time', Date.now().toString())
    },
    { token: E2E_JWT, user: portalUser },
  )
}

test.describe('CUJ-P10 Portal Field Work Inbox', () => {
  test.beforeEach(async ({ page }) => {
    await seedPortalSession(page)
  })

  test('home tile opens /portal/work and loads assigned_to=me', async ({ page }) => {
    const seen = await installPortalWorkMocks(page)
    await page.goto('/portal')
    await expect(page.getByTestId('portal-home')).toBeVisible()
    await page.getByTestId('portal-work-btn').click()
    await expect(page).toHaveURL(/\/portal\/work/)
    await expect(page.getByTestId('portal-work')).toBeVisible()
    await expect(page.getByTestId('portal-work-actions')).toBeVisible()
    await expect(page.getByText('Fix overdue CAPA')).toBeVisible()
    await expect.poll(() => seen.assignedToMe === true).toBeTruthy()
    await expect.poll(() => seen.byUserMe === true).toBeTruthy()
    await expect(page.getByTestId('portal-work-passport-linked')).toBeVisible()
    await expect(page.getByTestId('portal-work-reading')).toBeVisible()
  })

  test('unlinked engineer shows honest passport empty state', async ({ page }) => {
    await installPortalWorkMocks(page, { unlinked: true, emptyActions: true })
    await page.goto('/portal/work')
    await expect(page.getByTestId('portal-work-passport-unlinked')).toBeVisible()
    await expect(page.getByText(/Contact your supervisor/i)).toBeVisible()
    await expect(page.getByText(/No actions assigned to you/i)).toBeVisible()
  })
})
