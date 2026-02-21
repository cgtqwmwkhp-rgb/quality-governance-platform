import { Page } from '@playwright/test';

export async function mockApiEndpoints(page: Page) {
  // Mock auth
  await page.route('**/api/v1/auth/me', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1, email: 'test@example.com', first_name: 'Test', last_name: 'User',
        is_active: true, is_superuser: true, roles: ['admin'],
      }),
    })
  );

  // Mock common list endpoints with empty arrays
  const listEndpoints = [
    'incidents', 'risks', 'audits', 'complaints', 'documents',
    'policies', 'actions', 'notifications', 'users', 'investigations'
  ];
  for (const endpoint of listEndpoints) {
    await page.route(`**/api/v1/${endpoint}*`, route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }
      return route.continue();
    });
  }
}

export async function mockDashboardData(page: Page) {
  await page.route('**/api/v1/dashboard*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_incidents: 12, open_incidents: 3,
        total_risks: 24, high_risks: 5,
        total_audits: 8, overdue_audits: 1,
        compliance_score: 87.5,
      }),
    })
  );
}
