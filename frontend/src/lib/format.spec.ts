import { describe, expect, it } from 'vitest'

import { formatCurrency, formatRange } from '@/lib/format'

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
