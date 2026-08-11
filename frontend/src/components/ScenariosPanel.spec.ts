import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import ScenariosPanel from '@/components/ScenariosPanel.vue'
import type { ScenarioItem, ScenariosResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function scenario(overrides: Partial<ScenarioItem> = {}): ScenarioItem {
  return {
    units: 2,
    by_right: true,
    arv: 900000,
    total_cost: 597000,
    profit: 120000,
    margin: 0.22,
    roi: 0.2,
    max_allowable_offer: 145000,
    deal_score: 62,
    infeasible: false,
    ...overrides,
  }
}

function result(overrides: Partial<ScenariosResult> = {}): ScenariosResult {
  return {
    parcel_number: 'phl:000000001',
    by_right_units: 2,
    recommended_units: 2,
    scenarios: [scenario()],
    confidence: 'medium',
    reasons: [
      'By-right allows up to 2 unit(s); modeled 1-4 units (counts above by-right would need a variance or special exception).',
      '2 unit(s) by-right maximizes profit among the scenarios.',
    ],
    sources: [],
    computed_at: '2026-08-08T00:00:00Z',
    ...overrides,
  }
}

function render(scenarios: ScenariosResult) {
  setActivePinia(createPinia())
  useParcelStore().scenarios = scenarios
  return mount(ScenariosPanel, { global: { plugins: [Quasar] } })
}

describe('ScenariosPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('prices each unit count, not just its profit', () => {
    const wrapper = render(result())

    expect(wrapper.text()).toContain('Max offer')
    expect(wrapper.find('[data-test="scenario-mao-2"]').text()).toBe('$145,000')
  })

  it('withholds an offer figure where the build is not economical', () => {
    const wrapper = render(
      result({ scenarios: [scenario({ infeasible: true, max_allowable_offer: 0 })] }),
    )

    expect(wrapper.find('[data-test="scenario-mao-2"]').text()).toBe('—')
    expect(wrapper.text()).toContain('not economical')
  })

  it('states the basis for the unit count it stars', () => {
    const wrapper = render(result())

    expect(wrapper.find('[data-test="scenario-reasons"]').text()).toContain(
      '2 unit(s) by-right maximizes profit among the scenarios.',
    )
  })

  it('carries the hedge verbatim when the recommendation is only the least bad option', () => {
    const wrapper = render(
      result({
        reasons: ['3 unit(s) by-right is the least unprofitable on profit among the scenarios.'],
      }),
    )

    expect(wrapper.find('[data-test="scenario-reasons"]').text()).toContain(
      'is the least unprofitable on profit',
    )
  })

  it('keeps the informational framing alongside the figures', () => {
    expect(render(result()).text()).toContain('medium confidence · not financial advice.')
  })
})
