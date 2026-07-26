import { describe, it, expect } from 'vitest'
import { renderCopilotMarkdown } from '../CopilotMarkdown'

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
})
