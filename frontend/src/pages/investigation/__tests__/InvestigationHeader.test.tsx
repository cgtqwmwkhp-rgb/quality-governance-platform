import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import InvestigationHeader from '../InvestigationHeader'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, string | number>) => {
      if (key === 'investigations.identity.source_label') {
        return `Source: ${opts?.source} #${opts?.id}`
      }
      if (key === 'investigations.handoff.open_source_report') {
        return `Open source report (${opts?.source})`
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const investigation = {
  id: 7,
  reference_number: 'REF-2026-0003',
  template_id: 1,
  assigned_entity_type: 'reporting_incident' as const,
  assigned_entity_id: 99,
  title: 'Forklift investigation',
  description: 'Workspace description',
  status: 'in_progress' as const,
  data: {},
  created_at: '2026-03-01T10:00:00Z',
}

describe('InvestigationHeader identity chrome', () => {
  it('shows Investigation workspace eyebrow with REF as primary ID', () => {
    render(
      <BrowserRouter>
        <InvestigationHeader
          investigation={investigation}
          statusDisplay={{ label: 'In Progress', className: 'bg-info/10' }}
          EntityIcon={AlertTriangle}
          sourceLink={{ href: '/incidents/99', label: 'incident' }}
        />
      </BrowserRouter>,
    )

    expect(screen.getByTestId('investigation-role-eyebrow')).toHaveTextContent(
      'investigations.identity.eyebrow',
    )
    expect(screen.getByTestId('investigation-primary-ref')).toHaveTextContent('REF-2026-0003')
    expect(screen.getByTestId('investigation-purpose')).toHaveTextContent(
      'investigations.identity.purpose',
    )
    expect(screen.getByTestId('investigation-source-chip')).toHaveTextContent(
      'Source: incident #99',
    )
    expect(screen.getByTestId('investigation-open-source')).toHaveTextContent(
      'Open source report (incident)',
    )
  })
})
