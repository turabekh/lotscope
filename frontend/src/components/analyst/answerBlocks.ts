/**
 * The little of Markdown the Analyst actually writes, parsed into a render tree.
 *
 * Deliberately not a Markdown library and deliberately not v-html: the output is rendered
 * through ordinary Vue templates, so there is no way for model output to become markup.
 * It handles what shows up in real answers — paragraphs, bold spans, bullet lists and
 * pipe tables — and leaves anything else as plain text rather than mangling it.
 */

export interface Span {
  text: string
  bold: boolean
}

export type Block =
  | { kind: 'paragraph'; spans: Span[] }
  | { kind: 'list'; items: Span[][] }
  | { kind: 'table'; header: string[]; rows: string[][] }

const BOLD = /\*\*(.+?)\*\*/g

export function spansOf(line: string): Span[] {
  const spans: Span[] = []
  let index = 0
  for (const match of line.matchAll(BOLD)) {
    const at = match.index ?? 0
    if (at > index) spans.push({ text: line.slice(index, at), bold: false })
    spans.push({ text: match[1], bold: true })
    index = at + match[0].length
  }
  if (index < line.length) spans.push({ text: line.slice(index), bold: false })
  return spans.length ? spans : [{ text: line, bold: false }]
}

function isTableRow(line: string): boolean {
  return line.trim().startsWith('|') && line.trim().endsWith('|')
}

function isDivider(line: string): boolean {
  return /^\s*\|[\s:|-]+\|\s*$/.test(line)
}

function cells(line: string): string[] {
  return line
    .trim()
    .slice(1, -1)
    .split('|')
    .map((cell) => cell.trim())
}

export function parseAnswer(text: string): Block[] {
  const lines = text.split('\n')
  const blocks: Block[] = []
  let paragraph: string[] = []
  let items: Span[][] = []

  const flushParagraph = (): void => {
    if (paragraph.length) {
      blocks.push({ kind: 'paragraph', spans: spansOf(paragraph.join(' ')) })
      paragraph = []
    }
  }
  const flushList = (): void => {
    if (items.length) {
      blocks.push({ kind: 'list', items })
      items = []
    }
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    if (isTableRow(line) && i + 1 < lines.length && isDivider(lines[i + 1])) {
      flushParagraph()
      flushList()
      const header = cells(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(cells(lines[i]))
        i += 1
      }
      i -= 1
      blocks.push({ kind: 'table', header, rows })
      continue
    }

    const bullet = /^[-*]\s+(.*)$/.exec(trimmed)
    if (bullet) {
      flushParagraph()
      items.push(spansOf(bullet[1]))
      continue
    }

    flushList()
    paragraph.push(trimmed)
  }

  flushParagraph()
  flushList()
  return blocks
}
