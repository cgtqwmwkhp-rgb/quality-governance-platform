import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * Workforce calendar smoke (mocked APIs) — month/week/list + fetch honesty.
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

function scheduledInCurrentMonth(day: number): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const last = new Date(y, now.getMonth() + 1, 0).getDate()
  const d = String(Math.min(day, last)).padStart(2, '0')
  return `${y}-${m}-${d}`
}

async function installCalendarMocks(
  page: Page,
  opts?: { truncated?: boolean; failEngineers?: boolean },
) {
  const assessDate = scheduledInCurrentMonth(15)
  const inductDate = scheduledInCurrentMonth(16)

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    if (path.match(/\/engineers\/?$/) && method === 'GET') {
      if (opts?.failEngineers) {
        await json(route, { detail: 'Engineers offline' }, 503)
        return
      }
      await json(route, {
        items: [{ id: 7, employee_number: 'E-007', job_title: 'Tech', is_active: true }],
        total: 1,
        page: 1,
        page_size: 500,
      })
      return
    }

    if (path.match(/\/assessments\/?$/) && method === 'GET') {
      await json(route, {
        items: [
          {
            id: 'a-1',
            reference_number: 'ASS-001',
            engineer_id: 7,
            supervisor_id: 1,
            template_id: 1,
            status: 'scheduled',
            scheduled_date: assessDate,
            created_at: '2026-07-01T00:00:00Z',
          },
        ],
        total: opts?.truncated ? 520 : 1,
        page: 1,
        page_size: 500,
      })
      return
    }

    if (path.match(/\/inductions\/?$/) && method === 'GET') {
      await json(route, {
        items: [
          {
            id: 'i-1',
            reference_number: 'IND-001',
            engineer_id: 7,
            supervisor_id: 1,
            template_id: 1,
            stage: 'day1',
            status: 'in_progress',
            scheduled_date: inductDate,
            created_at: '2026-07-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 500,
      })
      return
    }

    await json(route, method === 'GET' ? { items: [], total: 0 } : { ok: true })
  })
}

async function openCalendar(page: Page, opts?: { truncated?: boolean; failEngineers?: boolean }) {
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, E2E_JWT)

  await installCalendarMocks(page, opts)
  await page.goto('/workforce/calendar', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('workforce-calendar')).toBeVisible({ timeout: 20_000 })
}

test.describe('Workforce calendar smoke', () => {
  test.use({ serviceWorkers: 'block' })

  test('month view shows events; week and list switch', async ({ page }) => {
    await openCalendar(page)

    await expect(page.getByTestId('calendar-month-view')).toBeVisible()
    await expect(page.getByText(/ASS-001/)).toBeVisible()

    await page.getByTestId('calendar-view-week').click()
    await expect(page.getByTestId('calendar-week-view')).toBeVisible()

    await page.getByTestId('calendar-view-list').click()
    await expect(page.getByTestId('calendar-list-view')).toBeVisible()
    await expect(page.getByText(/IND-001/)).toBeVisible()
  })

  test('click-through from list navigates to assessment execute', async ({ page }) => {
    await openCalendar(page)
    await page.getByTestId('calendar-view-list').click()
    await page.getByText(/ASS-001/).click()
    await expect(page).toHaveURL(/\/workforce\/assessments\/a-1\/execute/)
  })

  test('truncation honesty when total > page_size', async ({ page }) => {
    await openCalendar(page, { truncated: true })
    await expect(page.getByTestId('calendar-truncation-notice')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('calendar-truncation-notice')).toContainText(/truncated/i)
  })

  test('engineer-map failure surfaces warning (not silent)', async ({ page }) => {
    await openCalendar(page, { failEngineers: true })
    await expect(page.getByTestId('calendar-engineer-map-warning')).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByText(/ASS-001/)).toBeVisible()
  })
})
