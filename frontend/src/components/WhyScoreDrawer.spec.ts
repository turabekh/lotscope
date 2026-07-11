import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import WhyScoreDrawer from '@/components/WhyScoreDrawer.vue'
import type { VerdictResult } from '@/lib/types'

function makeVerdict(overrides: Partial<VerdictResult>): VerdictResult {
  return {
    parcel_number: '000000001',
    verdict_version: 'v8',
    buildability_score: 80,
    opportunity_score: 80,
    summary: 'RSA-5: buildable by-right (1 unit)',
    can_build_by_right: true,
    by_right_units: 1,
    max_height_ft: 38,
    needs_variance: false,
    buildable_area_sqft: 490,
    value_estimate_low: 150000,
    value_estimate_high: 320000,
    value_confidence: 0.6,
    assessment_market_gap: 40000,
    arv: null,
    est_profit: null,
    est_margin: null,
    max_allowable_offer: null,
    deal_score: null,
    is_underpriced: null,
    risk_score: 20,
    risk_flags: [
      {
        code: 'tax_delinquency',
        severity: 'high',
        label: 'Tax delinquent',
        detail: 'Owes 3 years of taxes.',
        source: 'tax_status',
      },
    ],
    sources: [{ dimension: 'risk', sources: [{ source: 'tax_status' }] }],
    computed_at: '2026-07-05T00:00:00Z',
    ...overrides,
  } as VerdictResult
}

async function drawerText(verdict: VerdictResult): Promise<string> {
  const wrapper = mount(WhyScoreDrawer, {
    props: { modelValue: true, verdict },
    global: { plugins: [[Quasar, {}]] },
  })
  await flushPromises()
  const text = document.body.textContent ?? ''
  wrapper.unmount()
  document.body.innerHTML = ''
  return text
}

describe('WhyScoreDrawer', () => {
  it('shows the score breakdown from stored components', async () => {
    const text = await drawerText(makeVerdict({ buildability_score: 80, risk_score: 20 }))
    expect(text).toContain('60% buildability + 40% low-risk')
    expect(text).toContain('80 × 0.6')
    expect(text).toContain('(100 − 20) × 0.4')
  })

  it('renders each risk flag with its detail, source, and weight', async () => {
    const text = await drawerText(makeVerdict({}))
    expect(text).toContain('Tax delinquent')
    expect(text).toContain('Owes 3 years of taxes.')
    expect(text).toContain('Revenue')
    expect(text).toContain('+40')
  })

  it('surfaces provenance — version, computed-at, and sources', async () => {
    const text = await drawerText(makeVerdict({}))
    expect(text).toContain('v8')
    expect(text).toContain('Revenue')
    expect(text).toContain('Informational only')
  })
})
