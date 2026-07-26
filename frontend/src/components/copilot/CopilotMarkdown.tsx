/**
 * Minimal markdown renderer for Copilot replies (PX-249).
 *
 * No new dependency: escapes HTML, then supports **bold**, bullet lists, and
 * GitHub-style pipe tables — the formats the demo replies actually emit.
 */

import React from 'react'

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function inlineBold(escaped: string): string {
  return escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

function isTableSeparator(line: string): boolean {
  return /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(line.trim())
}

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return trimmed.split('|').map((cell) => cell.trim())
}

function renderTable(rows: string[]): string {
  if (rows.length === 0) return ''
  const header = splitRow(rows[0]).map((cell) => `<th class="px-2 py-1 text-left font-medium">${inlineBold(escapeHtml(cell))}</th>`)
  const bodyRows = rows.slice(2).map((row) => {
    const cells = splitRow(row)
      .map((cell) => `<td class="px-2 py-1 border-t border-border">${inlineBold(escapeHtml(cell))}</td>`)
      .join('')
    return `<tr>${cells}</tr>`
  })
  return `<table class="w-full text-xs my-2 border-collapse"><thead><tr>${header.join('')}</tr></thead><tbody>${bodyRows.join('')}</tbody></table>`
}

export function renderCopilotMarkdown(source: string): string {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const html: string[] = []
  let i = 0
  let listOpen = false

  const closeList = () => {
    if (listOpen) {
      html.push('</ul>')
      listOpen = false
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    // Pipe table: header + separator + body
    if (
      line.includes('|') &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1])
    ) {
      closeList()
      const tableLines = [line, lines[i + 1]]
      i += 2
      while (i < lines.length && lines[i].includes('|')) {
        tableLines.push(lines[i])
        i += 1
      }
      html.push(renderTable(tableLines))
      continue
    }

    const bullet = line.match(/^\s*[•*-]\s+(.*)$/)
    if (bullet) {
      if (!listOpen) {
        html.push('<ul class="list-disc pl-4 my-1 space-y-0.5">')
        listOpen = true
      }
      html.push(`<li>${inlineBold(escapeHtml(bullet[1]))}</li>`)
      i += 1
      continue
    }

    closeList()

    if (line.trim() === '') {
      html.push('<br />')
    } else {
      html.push(`<p class="my-0.5">${inlineBold(escapeHtml(line))}</p>`)
    }
    i += 1
  }

  closeList()
  return html.join('')
}

interface CopilotMarkdownProps {
  content: string
  className?: string
}

export function CopilotMarkdown({ content, className }: CopilotMarkdownProps) {
  const html = React.useMemo(() => renderCopilotMarkdown(content), [content])
  return (
    <div
      className={className}
      data-testid="copilot-markdown"
      // Content is escaped before bold/table markup is applied.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

export default CopilotMarkdown
