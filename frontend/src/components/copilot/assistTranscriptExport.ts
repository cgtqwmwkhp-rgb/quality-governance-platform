/**
 * PlantEx Assist transcript export (FR-ASSIST-DEPTH-01 A4).
 *
 * Markdown download for the in-panel conversation. Absolute deeplinks use the
 * browser origin so exported transcripts open the SoR row outside the SPA.
 * PDF is deferred to print-to-PDF from the Markdown (no client PDF dependency).
 */

export interface AssistTranscriptMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt?: Date | string
}

function absolutiseMarkdownLinks(source: string, origin: string): string {
  const base = origin.replace(/\/$/, '')
  return source.replace(/\]\((\/[^)]+)\)/g, (_m, path: string) => `](${base}${path})`)
}

function roleHeading(role: AssistTranscriptMessage['role']): string {
  if (role === 'user') return 'Question'
  if (role === 'assistant') return 'Answer'
  return 'System'
}

/** Build a Markdown transcript suitable for download / print-to-PDF. */
export function buildAssistTranscriptMarkdown(
  messages: AssistTranscriptMessage[],
  options: { origin: string; title?: string; exportedAt?: Date } = {
    origin: typeof window !== 'undefined' ? window.location.origin : '',
  },
): string {
  const origin = (options.origin || '').replace(/\/$/, '')
  const title = options.title || 'PlantEx Assist transcript'
  const exportedAt = (options.exportedAt || new Date()).toISOString()
  const lines: string[] = [
    `# ${title}`,
    '',
    `Exported: ${exportedAt}`,
    '',
    'Answers are grounded on platform-computed register figures. Quoted references use absolute SoR links.',
    '',
  ]

  for (const message of messages) {
    if (message.role === 'system') continue
    const content =
      message.role === 'assistant'
        ? absolutiseMarkdownLinks(message.content, origin)
        : message.content
    lines.push(`## ${roleHeading(message.role)}`)
    lines.push('')
    lines.push(content.trim() || '_(empty)_')
    lines.push('')
  }

  return `${lines.join('\n').trim()}\n`
}

/** Trigger a Markdown file download in the browser. */
export function downloadAssistTranscriptMarkdown(
  markdown: string,
  filename = `plantex-assist-transcript-${new Date().toISOString().slice(0, 10)}.md`,
): void {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
