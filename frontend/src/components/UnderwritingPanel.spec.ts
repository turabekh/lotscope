import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UnderwritingPanel from '@/components/UnderwritingPanel.vue'
import { api } from '@/lib/api'
import type { UnderwritingAnalysis } from '@/lib/types'

function analysis(overrides: Partial<UnderwritingAnalysis> = {}): UnderwritingAnalysis {
  return {
    parcel_number: 'phl:1',
    assumptions: [
      {
        name: 'construction_cost_per_sqft',
        group: 'construction',
        value: 175,
        origin: 'platform_default',
        unit: 'money',
        limitations: null,
      },
      {
        name: 'target_margin',
        group: 'exit',
        value: 0.35,
        origin: 'user_override',
        unit: 'fraction',
        limitations: null,
      },
      {
        name: 'interest_rate',
        group: 'financing_and_time',
        value: null,
        origin: 'platform_default',
        unit: 'fraction',
        limitations: 'No Philadelphia financing rate has been supplied.',
      },
    ],
    mao: {
      formula: 'max_allowable_offer = (exit_value x (1 - selling_costs)) - costs',
      target_margin: 0.35,
      exclusions: ['financing interest, points, and loan fees'],
      unavailable_inputs: ['interest_rate'],
    },
    cases: [
      {
        case: 'downside',
        label: 'Downside',
        rationale: 'Value down 10%.',
        arv: 900000,
        total_cost: 700000,
        profit: 100000,
        margin: 0.11,
        max_allowable_offer: 90000,
        infeasible: false,
      },
      {
        case: 'base',
        label: 'Base',
        rationale: 'As modelled.',
        arv: 1000000,
        total_cost: 700000,
        profit: 200000,
        margin: 0.2,
        max_allowable_offer: 120000,
        infeasible: false,
      },
      {
        case: 'upside',
        label: 'Upside',
        rationale: 'Value up 10%.',
        arv: 1100000,
        total_cost: 690000,
        profit: 300000,
        margin: 0.28,
        max_allowable_offer: 150000,
        infeasible: false,
      },
    ],
    case_version: 'c1',
    computed_at: '2026-07-28T00:00:00Z',
    ...overrides,
  }
}

async function mountPanel(data: UnderwritingAnalysis) {
  vi.spyOn(api, 'getUnderwriting').mockResolvedValue(data)
  const wrapper = mount(UnderwritingPanel, {
    props: { parcelNumber: 'phl:1' },
    global: { plugins: [[Quasar, {}]] },
  })
  await flushPromises()
  return wrapper
}

describe('UnderwritingPanel', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('shows all three cases so downside is visible beside base', async () => {
    const text = (await mountPanel(analysis())).text()
    expect(text).toContain('Downside')
    expect(text).toContain('Base')
    expect(text).toContain('Upside')
  })

  it('names the inputs it could not obtain rather than hiding them', async () => {
    const wrapper = await mountPanel(analysis())
    const notice = wrapper.find('[data-test="unavailable-inputs"]')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('interest rate')
  })

  it('renders an uncalculated figure as not calculated, never as zero', async () => {
    const data = analysis()
    data.cases[0]!.max_allowable_offer = null
    const wrapper = await mountPanel(data)
    expect(wrapper.text()).toContain('Not calculated')
    expect(wrapper.text()).not.toContain('$0')
  })

  it('discloses the formula and exclusions on request', async () => {
    const wrapper = await mountPanel(analysis())
    expect(wrapper.find('[data-test="mao-disclosure"]').exists()).toBe(false)
    await wrapper.find('.disclose').trigger('click')
    const disclosure = wrapper.find('[data-test="mao-disclosure"]')
    expect(disclosure.text()).toContain('max_allowable_offer')
    expect(disclosure.text()).toContain('financing interest')
  })

  it('shows each assumption with where it came from', async () => {
    const wrapper = await mountPanel(analysis())
    await wrapper.find('.disclose').trigger('click')
    const text = wrapper.find('[data-test="mao-disclosure"]').text()
    expect(text).toContain('Platform default')
    expect(text).toContain('Your profile')
    expect(text).toContain('Unavailable')
  })

  it('tells the user how many assumptions came from their own profile', async () => {
    expect((await mountPanel(analysis())).text()).toContain('1 from your profile')
  })
})
