import { describe, expect, it } from 'vitest'

import {
  absoluteTileBaseUrl,
  formatCurrency,
  formatPercent,
  formatRange,
  marketCodeFromParcelNumber,
  scoreColor,
  scoreLabel,
  severityColor,
} from '@/lib/format'

describe('formatCurrency', () => {
  it('formats numbers as whole-dollar USD', () => {
    expect(formatCurrency(1500)).toBe('$1,500')
  })

  it('renders a dash for nullish values', () => {
    expect(formatCurrency(null)).toBe('—')
    expect(formatCurrency(undefined)).toBe('—')
  })
})

describe('formatRange', () => {
  it('joins a low/high range', () => {
    expect(formatRange(180000, 220000)).toBe('$180,000 – $220,000')
  })

  it('renders a dash when incomplete', () => {
    expect(formatRange(null, 220000)).toBe('—')
  })
})

describe('formatPercent', () => {
  it('renders a 0-1 fraction as a percentage', () => {
    expect(formatPercent(0.6)).toBe('60%')
    expect(formatPercent(null)).toBe('—')
  })
})

describe('scoreColor and scoreLabel', () => {
  it('maps opportunity score to colour bands', () => {
    expect(scoreColor(80)).toBe('positive')
    expect(scoreColor(50)).toBe('amber-8')
    expect(scoreColor(20)).toBe('negative')
    expect(scoreColor(null)).toBe('grey')
  })

  it('labels the score bands', () => {
    expect(scoreLabel(80)).toBe('Opportunity')
    expect(scoreLabel(20)).toBe('Caution')
  })
})

describe('severityColor', () => {
  it('maps risk severities and falls back', () => {
    expect(severityColor('high')).toBe('negative')
    expect(severityColor('medium')).toBe('warning')
    expect(severityColor('unknown')).toBe('grey-7')
  })
})

describe('marketCodeFromParcelNumber', () => {
  it('reads the market prefix', () => {
    expect(marketCodeFromParcelNumber('phl:000012345')).toBe('phl')
    expect(marketCodeFromParcelNumber('phl:875100090')).toBe('phl')
  })

  it('defaults to phl when there is no prefix', () => {
    expect(marketCodeFromParcelNumber('875100090')).toBe('phl')
  })
})

describe('absoluteTileBaseUrl', () => {
  it('resolves a relative path against the origin (MapLibre needs an absolute URL)', () => {
    expect(absoluteTileBaseUrl('/tiles', 'http://localhost:5173')).toBe(
      'http://localhost:5173/tiles',
    )
  })

  it('leaves an absolute url unchanged', () => {
    expect(absoluteTileBaseUrl('https://parcelphl.online/tiles', 'http://localhost:5173')).toBe(
      'https://parcelphl.online/tiles',
    )
  })
})
