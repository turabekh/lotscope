import { describe, expect, it } from 'vitest'

import { parseAnswer, spansOf } from '@/components/analyst/answerBlocks'

describe('spansOf', () => {
  it('marks bold runs and leaves the rest alone', () => {
    expect(spansOf('Screened **2026-09-16** today')).toEqual([
      { text: 'Screened ', bold: false },
      { text: '2026-09-16', bold: true },
      { text: ' today', bold: false },
    ])
  })

  it('leaves plain text plain', () => {
    expect(spansOf('nothing bold here')).toEqual([{ text: 'nothing bold here', bold: false }])
  })
})

describe('parseAnswer', () => {
  it('reads the pipe table the model actually writes', () => {
    const blocks = parseAnswer(
      [
        'Added the 3 BID lots:',
        '',
        '| Parcel | Address | Comp low |',
        '|---|---|---|',
        '| phl:463278700 | 902 S Cecil St | $50,000 |',
        '| phl:491370000 | 4851 N Warnock St | $22,600 |',
      ].join('\n'),
    )

    expect(blocks[0].kind).toBe('paragraph')
    const table = blocks[1]
    expect(table.kind).toBe('table')
    if (table.kind !== 'table') throw new Error('expected a table')
    expect(table.header).toEqual(['Parcel', 'Address', 'Comp low'])
    expect(table.rows).toHaveLength(2)
    expect(table.rows[1][1]).toBe('4851 N Warnock St')
  })

  it('reads bullet lists', () => {
    const blocks = parseAnswer('Caveats:\n\n- opening bids are nominal\n- water liens are absent')
    expect(blocks[1].kind).toBe('list')
    if (blocks[1].kind !== 'list') throw new Error('expected a list')
    expect(blocks[1].items).toHaveLength(2)
    expect(blocks[1].items[1][0].text).toContain('water liens')
  })

  it('joins wrapped lines into one paragraph', () => {
    const blocks = parseAnswer('a sentence that\nwrapped across lines')
    expect(blocks).toHaveLength(1)
    if (blocks[0].kind !== 'paragraph') throw new Error('expected a paragraph')
    expect(blocks[0].spans[0].text).toBe('a sentence that wrapped across lines')
  })

  it('leaves a lone pipe line as text rather than inventing a table', () => {
    const blocks = parseAnswer('the range is | low to high |')
    expect(blocks[0].kind).toBe('paragraph')
  })

  it('never produces markup from model output', () => {
    // The renderer takes spans and cells as text nodes, so this can only ever be shown,
    // never executed. The parser must not treat it as anything special either.
    const blocks = parseAnswer('<script>alert(1)</script> and **bold**')
    if (blocks[0].kind !== 'paragraph') throw new Error('expected a paragraph')
    expect(blocks[0].spans[0].text).toContain('<script>')
    expect(blocks[0].spans.some((span) => span.bold && span.text === 'bold')).toBe(true)
  })

  it('handles an empty answer without throwing', () => {
    expect(parseAnswer('')).toEqual([])
  })
})
