import { describe, expect, it } from 'vitest'

import {
  baseDistrictSummary,
  buildQualifier,
  byRightQualifier,
  outstandingCheckLabels,
  resolvePosture,
  unitCountLabel,
  unitCountNote,
  unitCountValue,
} from '@/lib/by-right'
import type { ChecklistItem, ParcelChecklist, VerdictResult } from '@/lib/types'

function item(code: string, category: string, status: ChecklistItem['status']): ChecklistItem {
  return { code, label: category, category, status, detail: '', source: null }
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
    program: null,
    posture: null,
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

describe('resolvePosture', () => {
  const verdict = (over: Partial<VerdictResult>) =>
    ({ summary: '', can_build_by_right: null, needs_variance: null, ...over }) as VerdictResult

  it('prefers the posture the backend resolved', () => {
    const list = { ...checklist([]), posture: 'master_plan_required' as const }
    expect(resolvePosture(verdict({ can_build_by_right: true }), list)).toBe('master_plan_required')
  })

  it('falls back to the summary only while no checklist has loaded', () => {
    const v = verdict({ summary: 'SP-PO-A: master plan required; 3 risk flag(s)' })
    expect(resolvePosture(v, null)).toBe('master_plan_required')
  })

  it('reads by-right and variance from the verdict when nothing else is available', () => {
    expect(resolvePosture(verdict({ can_build_by_right: true }), null)).toBe('by_right')
    expect(resolvePosture(verdict({ needs_variance: true }), null)).toBe('variance_required')
    expect(resolvePosture(verdict({}), null)).toBe('undetermined')
  })
})

describe('unit count claims', () => {
  it('does not call a count by-right when a variance is needed', () => {
    expect(unitCountLabel('variance_required')).toBe('Units if a variance is granted')
    expect(unitCountLabel('variance_required')).not.toContain('By-right')
    expect(unitCountNote('variance_required')).toContain('not available by right')
  })

  it('never shows a unit number for a master-plan district', () => {
    expect(unitCountValue('master_plan_required', 4)).toBe('None')
    expect(unitCountValue('master_plan_required', 4)).not.toContain('4')
  })

  it('keeps the plain label and value when the lot is by-right', () => {
    expect(unitCountLabel('by_right')).toBe('By-right units')
    expect(unitCountValue('by_right', 2)).toBe('2')
  })

  it('does not promise by-right units when conformance is unresolved', () => {
    expect(unitCountLabel('undetermined')).not.toContain('By-right')
  })
})

describe('buildQualifier', () => {
  it('states the master-plan requirement rather than a by-right screening', () => {
    const text = buildQualifier('master_plan_required', null)
    expect(text).toContain('not permitted by right')
    expect(text).not.toContain('dimensionally eligible')
  })

  it('names flagged checks under a by-right headline', () => {
    const text = buildQualifier(
      'by_right',
      checklist([
        item('a', 'L&I & demolition', 'fail'),
        item('b', 'Access & frontage', 'not_evaluated'),
      ]),
    )
    expect(text).toContain('Flagged for a closer look: L&I & demolition')
    expect(text).toContain('this eligibility may not hold')
    expect(text).toContain('Still to check: Access & frontage.')
  })

  it('omits the flagged clause when nothing is flagged', () => {
    const text = buildQualifier('by_right', checklist([item('a', 'Flood', 'not_evaluated')]))
    expect(text).not.toContain('Flagged for a closer look')
  })
})
