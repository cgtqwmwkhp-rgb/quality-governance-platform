import { test, expect } from '@playwright/test'

/**
 * CUJ — Document version control bar honesty (mocked APIs).
 * Create tip → revise opens draft → publish freezes prior as read-only.
 */
test.describe('Document version control CUJ', () => {
  test('document control shows create→revise→publish version history', async ({ page }) => {
    let detail = {
      id: 42,
      document_number: 'PRO-CUJVER1',
      title: 'Version Control CUJ Procedure',
      description: 'Prove immutable history',
      document_type: 'procedure',
      category: 'quality',
      subcategory: null,
      current_version: '1.0',
      status: 'draft',
      published_version: null,
      working_version: '1.0',
      department: null,
      author_name: 'Controller',
      owner_name: null,
      approver_name: null,
      approved_date: null,
      effective_date: null,
      expiry_date: null,
      review_frequency_months: 12,
      next_review_date: null,
      last_review_date: null,
      file_name: null,
      file_path: null,
      file_size: null,
      file_type: null,
      relevant_standards: null,
      relevant_clauses: null,
      access_level: 'internal',
      is_confidential: false,
      training_required: false,
      view_count: 0,
      download_count: 0,
      versions: [
        {
          id: 1,
          version_number: '1.0',
          change_summary: 'Initial document creation',
          change_type: 'new',
          status: 'draft',
          is_immutable: false,
          read_only: false,
          created_by_name: 'Controller',
          created_at: '2026-07-13T09:00:00Z',
          approved_by_name: null,
          approved_date: null,
        },
      ],
      distributions: [],
    }

    await page.route('**/api/v1/document-control/**', async (route) => {
      const req = route.request()
      const url = req.url()
      const method = req.method()

      if (method === 'GET' && url.match(/document-control\/?\?/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total: 1,
            documents: [
              {
                id: 42,
                document_number: detail.document_number,
                title: detail.title,
                document_type: detail.document_type,
                category: detail.category,
                current_version: detail.current_version,
                status: detail.status,
                department: null,
                owner_name: null,
                effective_date: null,
                next_review_date: null,
                is_overdue: false,
              },
            ],
          }),
        })
        return
      }

      if (method === 'GET' && url.includes('/document-control/42')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(detail),
        })
        return
      }

      if (method === 'POST' && url.includes('/document-control/42/publish')) {
        detail = {
          ...detail,
          status: 'published',
          current_version: '1.0',
          published_version: '1.0',
          working_version: null,
          versions: [
            {
              ...detail.versions[0],
              status: 'published',
              is_immutable: true,
              read_only: true,
              approved_by_name: 'Controller',
              approved_date: '2026-07-13T10:00:00Z',
            },
          ],
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 42,
            current_version: '1.0',
            status: 'published',
            version: detail.versions[0],
            message: 'Version 1.0 published',
          }),
        })
        return
      }

      if (method === 'POST' && url.includes('/document-control/42/versions')) {
        detail = {
          ...detail,
          status: 'under_revision',
          current_version: '1.1',
          published_version: '1.0',
          working_version: '1.1',
          versions: [
            {
              id: 2,
              version_number: '1.1',
              change_summary: 'Clarify inspection cadence after audit finding',
              change_type: 'revision',
              status: 'draft',
              is_immutable: false,
              read_only: false,
              created_by_name: 'Controller',
              created_at: '2026-07-13T11:00:00Z',
              approved_by_name: null,
              approved_date: null,
            },
            {
              ...detail.versions[0],
              status: 'published',
              is_immutable: true,
              read_only: true,
            },
          ],
        }
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2,
            version_number: '1.1',
            status: 'draft',
            is_immutable: false,
            read_only: false,
            message: 'Version 1.1 created',
          }),
        })
        return
      }

      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    })

    await page.goto('/document-control')
    await expect(page.getByText('PRO-CUJVER1')).toBeVisible()
    await page.getByText('Version Control CUJ Procedure').click()

    const bar = page.getByTestId('document-version-control-bar')
    await expect(bar).toBeVisible()
    await expect(page.getByTestId('version-tip')).toContainText('v1.0')
    await expect(page.getByTestId('version-working')).toContainText('v1.0')

    await page.getByTestId('version-publish-btn').click()
    await expect(page.getByTestId('version-doc-status')).toContainText('published')
    await expect(page.getByTestId('version-immutable-1.0')).toBeVisible()

    await page.getByTestId('version-revise-btn').click()
    await page.getByTestId('version-change-summary').fill(
      'Clarify inspection cadence after audit finding',
    )
    await page.getByTestId('version-revise-submit').click()
    await expect(page.getByTestId('version-tip')).toContainText('v1.1')
    await expect(page.getByTestId('version-row-1.1')).toBeVisible()
    await expect(page.getByTestId('version-immutable-1.0')).toBeVisible()
  })
})
