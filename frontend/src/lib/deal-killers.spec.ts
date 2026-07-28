import { describe, expect, it } from 'vitest'

import { DEAL_KILLER_LIMIT, rankedDealKillers } from '@/lib/deal-killers'

describe('deal killer ranking', () => {
  it('ranks by severity, then by decision impact', () => {
    const ranked = rankedDealKillers([
      { code: 'historic_district', label: 'Historic', severity: 'high' },
      { code: 'no_street_access', label: 'No access', severity: 'high' },
      { code: 'tax_delinquent', label: 'Delinquent', severity: 'medium' },
    ])
    expect(ranked.map((f) => f.code)).toEqual([
      'no_street_access',
      'historic_district',
      'tax_delinquent',
    ])
  })

  it('shows no more than three, and drops nothing silently from the record', () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      code: `c${i}`,
      label: `Flag ${i}`,
      severity: 'high',
    }))
    expect(rankedDealKillers(many)).toHaveLength(DEAL_KILLER_LIMIT)
  })

  it('excludes informational flags from the deal-killer row', () => {
    const ranked = rankedDealKillers([{ code: 'note', label: 'Note', severity: 'info' }])
    expect(ranked).toEqual([])
  })

  it('survives malformed flags rather than throwing on a dossier', () => {
    expect(rankedDealKillers([null, 'x', 42, {}] as unknown[])).toEqual([])
  })

  it('is deterministic when severity and impact tie', () => {
    const ranked = rankedDealKillers([
      { code: 'b', label: 'B', severity: 'low' },
      { code: 'a', label: 'A', severity: 'low' },
    ])
    expect(ranked.map((f) => f.code)).toEqual(['a', 'b'])
  })
})
