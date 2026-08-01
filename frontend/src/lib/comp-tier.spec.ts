import { describe, expect, it } from 'vitest'

import { isWideAreaValuation, wideAreaSearchNote } from '@/lib/comp-tier'
import type { VerdictResult } from '@/lib/types'

function verdict(sources: unknown[]): VerdictResult {
  return { sources } as VerdictResult
}

const WIDE = [
  {
    dimension: 'valuation',
    sources: [{ source: 'rtt_summary', comp_tier: 'wide_area', radius_ft: 3000, years: 5 }],
  },
]

const LOCAL = [
  {
    dimension: 'valuation',
    sources: [{ source: 'rtt_summary', comp_tier: 'local', radius_ft: 1500, years: 3 }],
  },
]

describe('comp tier', () => {
  it('detects a wide-area valuation', () => {
    expect(isWideAreaValuation(verdict(WIDE))).toBe(true)
  })

  it('does not flag a local valuation', () => {
    expect(isWideAreaValuation(verdict(LOCAL))).toBe(false)
    expect(wideAreaSearchNote(verdict(LOCAL))).toBeNull()
  })

  it('names the radius and lookback actually used', () => {
    const note = wideAreaSearchNote(verdict(WIDE))
    expect(note).toContain('3,000 ft')
    expect(note).toContain('5 years')
    expect(note).toContain('rough guide')
  })

  it('falls back to a plain sentence when the numbers are missing', () => {
    const note = wideAreaSearchNote(
      verdict([{ dimension: 'valuation', sources: [{ comp_tier: 'wide_area' }] }]),
    )
    expect(note).toBe('No land sales were found close by, so this uses a wider search.')
  })

  it('ignores other dimensions and survives malformed provenance', () => {
    expect(
      isWideAreaValuation(verdict([{ dimension: 'risk', sources: [{ comp_tier: 'wide_area' }] }])),
    ).toBe(false)
    expect(isWideAreaValuation(verdict([]))).toBe(false)
    expect(isWideAreaValuation({ sources: null } as unknown as VerdictResult)).toBe(false)
    expect(isWideAreaValuation(verdict([null, 'nonsense']))).toBe(false)
  })
})
