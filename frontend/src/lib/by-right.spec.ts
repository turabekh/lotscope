import { describe, expect, it } from 'vitest'

import { baseDistrictSummary, byRightQualifier, outstandingCheckLabels } from '@/lib/by-right'
import type { ChecklistItem, ParcelChecklist, VerdictResult } from '@/lib/types'

function item(code: string, category: string, status: ChecklistItem['status']): ChecklistItem {
  return { code, category, status, detail: '', source: null }
}

function checklist(items: ChecklistItem[]): ParcelChecklist {
  return {
    parcel_number: 'phl:1',
    items,
    summary: {
      not_evaluated: items.filter((i) => i.status === 'not_evaluated').length,
      passed: items.filter((i) => i.status === 'pass').length,
      warnings: 0,
      failures: 0,
      info: 0,
      ready: true,
    },
    buildability_confidence: 'high',
    buildability_confidence_reasons: [],
    computed_at: '2026-08-01T00:00:00Z',
  }
}

describe('outstandingCheckLabels', () => {
  it('returns only the not-evaluated categories', () => {
    const result = outstandingCheckLabels(
      checklist([
        item('a', 'Liens & taxes', 'pass'),
        item('b', 'Access & frontage', 'not_evaluated'),
        item('c', 'Flood & environmental', 'not_evaluated'),
        item('d', 'Historic & overlays', 'potential_issue'),
      ]),
    )
    expect(result).toEqual(['Access & frontage', 'Flood & environmental'])
  })

  it('deduplicates categories spanning several items', () => {
    const result = outstandingCheckLabels(
      checklist([
        item('a', 'Access & frontage', 'not_evaluated'),
        item('b', 'Access & frontage', 'not_evaluated'),
      ]),
    )
    expect(result).toEqual(['Access & frontage'])
  })

  it('returns nothing when there is no checklist', () => {
    expect(outstandingCheckLabels(null)).toEqual([])
  })
})

describe('byRightQualifier', () => {
  it('never presents the base-district pass as approval', () => {
    const text = byRightQualifier(checklist([item('a', 'Access & frontage', 'not_evaluated')]))
    expect(text).toContain('preliminary screening, not a construction approval')
    expect(text.toLowerCase()).not.toContain('approved')
    expect(text.toLowerCase()).not.toContain('permitted to build')
  })

  it('names the outstanding checks alongside the qualifier', () => {
    const text = byRightQualifier(
      checklist([
        item('a', 'Access & frontage', 'not_evaluated'),
        item('b', 'Ownership & title', 'not_evaluated'),
      ]),
    )
    expect(text).toContain('Still to check: Access & frontage, Ownership & title.')
  })

  it('still qualifies when no checklist has loaded', () => {
    const text = byRightQualifier(null)
    expect(text).toContain('preliminary screening, not a construction approval')
    expect(text).toContain('Still to check: overlays, access, utilities, and title.')
  })
})

describe('baseDistrictSummary', () => {
  it('describes the district standard rather than a permission', () => {
    const verdict = { by_right_units: 3 } as VerdictResult
    expect(baseDistrictSummary(verdict)).toBe('Base district permits 3 units')
  })

  it('singularises one unit', () => {
    const verdict = { by_right_units: 1 } as VerdictResult
    expect(baseDistrictSummary(verdict)).toBe('Base district permits 1 unit')
  })

  it('falls back when no unit count resolved', () => {
    const verdict = { by_right_units: null } as VerdictResult
    expect(baseDistrictSummary(verdict)).toBe('Base district standards met')
  })
})
