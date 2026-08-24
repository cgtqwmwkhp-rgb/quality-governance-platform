import { describe, it, expect } from 'vitest'
import { renderCopilotMarkdown } from '../CopilotMarkdown'
import {
  buildAssistTranscriptMarkdown,
} from '../assistTranscriptExport'

describe('renderCopilotMarkdown', () => {
  it('escapes HTML and renders bold', () => {
    const html = renderCopilotMarkdown('Hello **world** <script>x</script>')
    expect(html).toContain('<strong>world</strong>')
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toContain('<script>')
  })

  it('renders pipe tables without leaving raw pipes as the only representation', () => {
    const source = [
      '| Level | Count |',
      '|-------|-------|',
      '| High | 8 |',
    ].join('\n')
    const html = renderCopilotMarkdown(source)
    expect(html).toContain('<table')
    expect(html).toContain('<th')
    expect(html).toContain('High')
    expect(html).toContain('8')
  })

  it('renders in-app SoR deeplinks', () => {
    const html = renderCopilotMarkdown('See [INC-2026-0001](/incidents/10).')
    expect(html).toContain('data-testid="copilot-deeplink"')
    expect(html).toContain('href="/incidents/10"')
    expect(html).toContain('INC-2026-0001')
  })

  it('does not render unsafe link schemes as anchors', () => {
    const html = renderCopilotMarkdown('Bad [x](javascript:alert(1))')
    expect(html).not.toContain('<a ')
    expect(html).toContain('javascript:alert(1)')
  })
})

describe('buildAssistTranscriptMarkdown', () => {
  it('absolutises relative deeplinks for export', () => {
    const md = buildAssistTranscriptMarkdown(
      [
        { role: 'user', content: 'How many incidents?' },
        {
          role: 'assistant',
          content: 'Total **2**.\n\nReferences: [INC-2026-0001](/incidents/10).',
        },
      ],
      { origin: 'https://app.example.test', exportedAt: new Date('2026-08-11T12:00:00.000Z') },
    )
    expect(md).toContain('# PlantEx Assist transcript')
    expect(md).toContain('## Question')
    expect(md).toContain('## Answer')
    expect(md).toContain('[INC-2026-0001](https://app.example.test/incidents/10)')
    expect(md).not.toContain('](/incidents/10)')
  })
})
