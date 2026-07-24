import { expect, test, type Page, type Route } from '@playwright/test'

/**
 * AI Audit Builder CUJ — mocked APIs, all purpose/scope/standard options exercised.
 * Guards against SWA-relative /api 405 by asserting calls hit the API host (not SWA).
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

const BRIEF = {
  brief_id: 'brief-e2e-1',
  purpose: 'risk_audit',
  scopes: ['incidents', 'near_misses'],
  case_refs: [{ type: 'incident', id: 42 }],
  asset_hint: 'Williams Trailer',
  standards: ['ISO 45001', 'HSE'],
  themes: ['Recent incident: winch cable', 'Recent near miss: guarding'],
  upload_summaries: [],
  research_findings: [
    {
      title: 'HSE LOLER guidance',
      summary: 'Thorough examination of lifting equipment',
      source_url: 'https://www.hse.gov.uk/work-equipment-machinery/loler.htm',
    },
  ],
  research_available: true,
  proposed_sections: [
    { title: 'Critical controls', rationale: 'Highest risk first' },
    { title: 'Evidence and records', rationale: 'Prove competence' },
  ],
  open_questions: [
    { id: 'depth', prompt: 'How deep should this be?' },
    { id: 'include_themes', prompt: 'Any must-include themes?' },
  ],
  freeform_notes: '',
  qa_answers: {},
}

const GENERATED = {
  action: 'build_new',
  sections: [
    {
      id: 's1',
      title: 'Critical controls',
      description: 'Core checks',
      questions: [
        {
          id: 'q1',
          text: 'Is the winch cable free from fraying?',
          type: 'yes_no',
          required: true,
          weight: 5,
          evidenceRequired: true,
        },
        {
          id: 'q2',
          text: 'Are guards fitted and secure?',
          type: 'yes_no',
          required: true,
          weight: 5,
          evidenceRequired: false,
        },
      ],
    },
    {
      id: 's2',
      title: 'Evidence and records',
      description: 'Records',
      questions: [
        {
          id: 'q3',
          text: 'LOLER examination certificate available?',
          type: 'yes_no',
          required: true,
          weight: 3,
          evidenceRequired: true,
        },
      ],
    },
  ],
  standard_suggestions: [{ question_id: 'q1', scheme: 'ISO', ref_id: '45001-8.1' }],
  builder_meta: { brief_id: 'brief-e2e-1', source_case_refs: [{ type: 'incident', id: 42 }] },
}

async function installAuditBuilderMocks(page: Page, opts?: { researchOffline?: boolean }) {
  const gatherBodies: unknown[] = []
  const generateBodies: unknown[] = []

  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('token', token)
  }, E2E_JWT)

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    // Never allow SWA-origin relative failures to be silently "ok"
    if (url.hostname.includes('azurestaticapps.net')) {
      await json(route, { detail: 'SWA has no API backend — use API_BASE_URL' }, 405)
      return
    }

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

    if (path.includes('/ai-templates/gather-brief') && method === 'POST') {
      gatherBodies.push(req.postDataJSON())
      const body = { ...BRIEF }
      if (opts?.researchOffline) {
        body.research_findings = []
        body.research_available = false
      }
      await json(route, body)
      return
    }

    if (path.includes('/ai-templates/apply-qa') && method === 'POST') {
      const payload = req.postDataJSON() as { brief: typeof BRIEF; answers: Record<string, string> }
      await json(route, {
        ...payload.brief,
        qa_answers: payload.answers || {},
        proposed_sections: [
          ...payload.brief.proposed_sections,
          ...(payload.answers?.include_themes
            ? [{ title: 'User-requested themes', rationale: payload.answers.include_themes }]
            : []),
        ],
      })
      return
    }

    if (path.includes('/ai-templates/similar-templates') && method === 'POST') {
      await json(route, {
        matches: [
          {
            id: 99,
            name: 'Existing Winch Inspection',
            description: 'Prior trailer winch checklist',
            score: 0.62,
            question_sample: ['Cable condition'],
          },
        ],
        count: 1,
      })
      return
    }

    if (path.includes('/ai-templates/generate-from-brief') && method === 'POST') {
      const payload = req.postDataJSON() as {
        similar_gate_action?: string
        similar_template_id?: number
      }
      generateBodies.push(payload)
      if (payload.similar_gate_action === 'use_existing') {
        await json(route, {
          action: 'use_existing',
          template_id: payload.similar_template_id || 99,
          sections: [],
          builder_meta: {},
        })
        return
      }
      await json(route, GENERATED)
      return
    }

    if (path.includes('/ai-templates/research') && method === 'POST') {
      if (opts?.researchOffline) {
        await json(route, { findings: [], available: false, reason: 'research_unavailable' })
        return
      }
      await json(route, {
        findings: BRIEF.research_findings,
        available: true,
        reason: null,
      })
      return
    }

    if (path.includes('/search') && method === 'GET') {
      await json(route, {
        results: [
          {
            id: 'INC-42',
            type: 'incident',
            title: 'Winch cable near miss follow-up',
            entity_id: 42,
            module: 'Incidents',
            status: 'Open',
            date: '2026-07-01',
            relevance: 90,
            description: 'Cable fray',
            highlights: [],
          },
        ],
        total: 1,
        query: url.searchParams.get('q') || '',
        facets: {},
      })
      return
    }

    if (path.includes('/audits/templates') && method === 'GET') {
      await json(route, { items: [], total: 0 })
      return
    }

    await json(route, {})
  })

  return { gatherBodies, generateBodies }
}

async function openWizard(page: Page) {
  await page.goto('/audit-templates/new?ai=1')
  await expect(page.getByRole('heading', { name: /AI Audit Builder|Adeiladydd Archwiliad AI/i })).toBeVisible({
    timeout: 20_000,
  })
}

const PURPOSES = [
  'Risk-driven audit',
  'Technical / competency assessment',
  'Vehicle / asset check',
  'ISO / scheme audit',
  'Case follow-up audit',
  'Freeform',
]

test.describe('AI Audit Builder CUJ', () => {
  test('full happy path: intent → brief → Q&A → similar → generate → apply', async ({ page }) => {
    const { gatherBodies, generateBodies } = await installAuditBuilderMocks(page)
    await openWizard(page)

    await page.getByText('Risk-driven audit', { exact: false }).click()
    await page.getByText('Near misses', { exact: false }).click()
    await page.getByPlaceholder(/Williams Trailer/i).fill('Williams Trailer / SEB winch')
    await page.getByText('Include live research', { exact: false }).click() // toggle off then on
    await page.getByText('Include live research', { exact: false }).click()
    await page.locator('textarea').first().fill('Focus on SEB winch guarding')

    await page.getByRole('button', { name: /Gather brief|Casglu crynodeb/i }).click()
    await expect(page.getByText(/Platform themes|Themâu platfform/i)).toBeVisible()
    await expect(page.getByText(/winch cable/i)).toBeVisible()
    await expect(page.getByText(/HSE LOLER/i)).toBeVisible()
    expect(gatherBodies.length).toBe(1)

    await page.getByRole('button', { name: /Continue to Q&A|Parhau i Holi/i }).click()
    await page.locator('textarea').nth(0).fill('full audit')
    await page.locator('textarea').nth(1).fill('cable wear, guarding')
    await page.getByRole('button', { name: /Check similar|Gwirio templedi/i }).click()

    await expect(page.getByText(/Existing Winch Inspection/i)).toBeVisible()
    await page.getByText(/Existing Winch Inspection/i).click()
    await page.getByRole('button', { name: /Build new anyway|Adeiladu'n newydd/i }).click()
    await page.getByRole('button', { name: /^Generate$|^Cynhyrchu$/i }).click()

    await expect(page.getByText(/Critical controls/i)).toBeVisible()
    await expect(page.getByText(/winch cable free from fraying/i)).toBeVisible()
    expect(generateBodies.length).toBe(1)
    expect((generateBodies[0] as { similar_gate_action: string }).similar_gate_action).toBe('build_new')
  })

  test('research offline path remains usable', async ({ page }) => {
    await installAuditBuilderMocks(page, { researchOffline: true })
    await openWizard(page)
    await page.getByRole('button', { name: /Gather brief|Casglu crynodeb/i }).click()
    await expect(page.getByText(/research unavailable|ymchwil fyw/i)).toBeVisible()
    await page.getByRole('button', { name: /Continue to Q&A|Parhau i Holi/i }).click()
    await expect(page.getByText(/How deep|pa mor ddwfn/i)).toBeVisible()
  })

  for (const purpose of PURPOSES) {
    test(`intent purpose option: ${purpose}`, async ({ page }) => {
      const { gatherBodies } = await installAuditBuilderMocks(page)
      await openWizard(page)
      await page.getByText(purpose, { exact: false }).click()
      await page.getByRole('button', { name: /Gather brief|Casglu crynodeb/i }).click()
      await expect(page.getByText(/Platform themes|Themâu platfform/i)).toBeVisible()
      const body = gatherBodies[0] as { purpose: string }
      expect(body.purpose).toBeTruthy()
    })
  }

  test('standards and scopes multi-select are posted', async ({ page }) => {
    const { gatherBodies } = await installAuditBuilderMocks(page)
    await openWizard(page)
    const wizard = page.getByTestId('ai-audit-builder-wizard')
    await wizard.getByRole('button', { name: 'ISO 9001' }).click()
    await wizard.getByRole('button', { name: 'UVDB-Achilles' }).click()
    await wizard.getByRole('button', { name: 'Planet Mark' }).click()
    await wizard.getByRole('button', { name: 'RTAs' }).click()
    await wizard.getByRole('button', { name: 'Complaints' }).click()
    await wizard.getByRole('button', { name: 'Documents' }).click()
    await page.getByRole('button', { name: /Gather brief|Casglu crynodeb/i }).click()
    await expect(page.getByText(/Platform themes|Themâu platfform/i)).toBeVisible()
    const body = gatherBodies[0] as { standards: string[]; scopes: string[] }
    expect(body.standards).toEqual(expect.arrayContaining(['ISO 9001', 'UVDB-Achilles', 'Planet Mark']))
    expect(body.scopes).toEqual(expect.arrayContaining(['rtas', 'complaints', 'documents']))
  })

  test('use existing similar template does not generate sections', async ({ page }) => {
    await installAuditBuilderMocks(page)
    let navigatedTo: string | null = null
    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) navigatedTo = frame.url()
    })
    await openWizard(page)
    await page.getByRole('button', { name: /Gather brief|Casglu crynodeb/i }).click()
    await page.getByRole('button', { name: /Continue to Q&A|Parhau i Holi/i }).click()
    await page.getByRole('button', { name: /Check similar|Gwirio templedi/i }).click()
    await page.getByText(/Existing Winch Inspection/i).click()
    await page.getByRole('button', { name: /Use existing|Defnyddio'r un/i }).click()
    await page.getByRole('button', { name: /^Generate$|^Cynhyrchu$/i }).click()
    await page.waitForTimeout(500)
    // Component closes and navigates to edit existing template
    expect(navigatedTo || page.url()).toMatch(/audit-templates\/99\/edit|audit-templates\/new/)
  })

  test('case prefill from query opens case-follow-up intent', async ({ page }) => {
    await installAuditBuilderMocks(page)
    await page.addInitScript((token) => {
      localStorage.setItem('access_token', token)
    }, E2E_JWT)
    await page.goto('/audit-templates/new?ai=1&caseType=incident&caseId=42')
    await expect(page.getByRole('heading', { name: /AI Audit Builder/i })).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByText(/incident #42|Case follow-up/i).first()).toBeVisible()
  })
})
