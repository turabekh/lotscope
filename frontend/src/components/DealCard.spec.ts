import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DealCard from '@/components/DealCard.vue'
import type { DealResult, ParcelDetail, SensitivityGrid, UnderwritingAnalysis } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function deal(overrides: Partial<DealResult> = {}): DealResult {
  return {
    parcel_number: 'phl:000000001',
    units: 2,
    arv: 900000,
    per_unit_value: 450000,
    gross_floor_area_sqft: 2400,
    acquisition_cost: 60000,
    construction_cost: 420000,
    soft_cost: 63000,
    selling_cost: 54000,
    total_cost: 597000,
    profit: 120000,
    margin: 0.22,
    roi: 0.2,
    max_allowable_offer: 145000,
    is_underpriced: false,
    deal_score: 62,
    infeasible: false,
    comp_count: 7,
    confidence: 'medium',
    assumptions: {
      construction_cost_per_sqft: 175,
      soft_cost_pct: 0.15,
      selling_cost_pct: 0.06,
      target_margin: 0.2,
      default_unit_sqft: 1200,
      max_unit_sqft: 3000,
    },
    reasons: ['Modelled 2 by-right units from the district standard.'],
    sources: [],
    computed_at: '2026-08-08T00:00:00Z',
    ...overrides,
  } as DealResult
}

function grid(): SensitivityGrid {
  const exits = [0.85, 0.925, 1.0, 1.075, 1.15]
  const costs = [0.9, 0.95, 1.0, 1.05, 1.1]
  return {
    available: true,
    unavailable_reason: null,
    row_label: 'Finished value',
    column_label: 'Construction cost',
    exit_multipliers: exits,
    cost_multipliers: costs,
    cells: exits.flatMap((e) =>
      costs.map((c) => ({
        exit_multiplier: e,
        cost_multiplier: c,
        margin: 0.2,
        profit: 90000,
        infeasible: false,
      })),
    ),
  }
}

function analysis(overrides: Partial<UnderwritingAnalysis> = {}): UnderwritingAnalysis {
  return {
    parcel_number: 'phl:000000001',
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
        name: 'soft_cost_pct',
        group: 'construction',
        value: 0.15,
        origin: 'market_default',
        unit: 'fraction',
        limitations: null,
      },
      {
        name: 'target_margin',
        group: 'exit',
        value: 0.2,
        origin: 'user_override',
        unit: 'fraction',
        limitations: null,
      },
      {
        name: 'default_unit_sqft',
        group: 'development_program',
        value: 1200,
        origin: 'derived',
        unit: 'sqft',
        limitations: null,
      },
      {
        name: 'max_unit_sqft',
        group: 'development_program',
        value: 3000,
        origin: 'scenario_override',
        unit: 'sqft',
        limitations: null,
      },
      {
        name: 'assessed_value',
        group: 'acquisition',
        value: 90000,
        origin: 'authoritative_source',
        unit: 'money',
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
      target_margin: 0.2,
      exclusions: ['financing interest, points, and loan fees', 'carrying costs'],
      unavailable_inputs: ['interest_rate'],
    },
    cases: [
      {
        case: 'downside',
        label: 'Downside',
        rationale: 'Value down 10%.',
        arv: 810000,
        total_cost: 597000,
        profit: 60000,
        margin: 0.09,
        max_allowable_offer: 90000,
        infeasible: false,
      },
      {
        case: 'base',
        label: 'Base',
        rationale: 'As modelled.',
        arv: 900000,
        total_cost: 597000,
        profit: 120000,
        margin: 0.22,
        max_allowable_offer: 145000,
        infeasible: false,
      },
      {
        case: 'upside',
        label: 'Upside',
        rationale: 'Value up 10%.',
        arv: 990000,
        total_cost: 597000,
        profit: 190000,
        margin: 0.3,
        max_allowable_offer: 190000,
        infeasible: false,
      },
    ],
    case_version: 'c1',
    sensitivity: grid(),
    computed_at: '2026-08-08T00:00:00Z',
    ...overrides,
  } as UnderwritingAnalysis
}

function render(
  dealValue: DealResult | null,
  underwritingValue: UnderwritingAnalysis | null = analysis(),
) {
  setActivePinia(createPinia())
  const store = useParcelStore()
  store.detail = { parcel_number: 'phl:000000001' } as ParcelDetail
  store.deal = dealValue
  store.underwriting = underwritingValue
  return mount(DealCard, { global: { plugins: [Quasar] } })
}

describe('DealCard — hero and provenance', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('states the offer as advice-shaped guidance, not a bare number', () => {
    const text = render(deal()).text()

    expect(text).toContain('Offer up to')
    expect(text).toContain('$145,000')
    expect(text).toContain('to clear a 20% margin')
  })

  it('keeps the informational disclaimer directly under the hero', () => {
    expect(render(deal()).text()).toContain(
      'Informational only — not an appraisal, and not legal or financial advice.',
    )
  })

  it('composes provenance from real fields', () => {
    const text = render(deal()).find('[data-test="deal-provenance"]').text()

    expect(text).toContain('ARV from 7 improved-sale comps')
    expect(text).not.toContain('based on 7 comps')
    expect(text).toContain('20% target margin')
  })

  it('names the scenario as the cost source when one is set', () => {
    expect(render(deal()).find('[data-test="deal-provenance"]').text()).toContain(
      'costs you set for this scenario',
    )
  })

  it('falls back to the profile when no scenario override is present', () => {
    const withoutScenario = analysis({
      assumptions: analysis().assumptions.filter((a) => a.origin !== 'scenario_override'),
    })

    expect(render(deal(), withoutScenario).find('[data-test="deal-provenance"]').text()).toContain(
      'your profile costs',
    )
  })

  it('says no viable price rather than showing a zero hero when infeasible', () => {
    const text = render(deal({ infeasible: true, max_allowable_offer: 0 })).text()

    expect(text).toContain('No viable price')
    expect(text).not.toContain('Offer up to')
    expect(text).toContain('not economical here at any land price')
  })

  it('keeps the underpriced banner', () => {
    expect(render(deal({ is_underpriced: true })).text()).toContain('looks underpriced')
  })
})

describe('DealCard — trust surfaces preserved', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('(1) renders the plain-English reasons list', () => {
    const wrapper = render(deal({ reasons: ['Reason one.', 'Reason two.'] }))

    const items = wrapper.findAll('.reason-list li').map((li) => li.text())
    expect(items).toEqual(['Reason one.', 'Reason two.'])
  })

  it('(2) labels every assumption origin in human words', () => {
    const text = render(deal()).find('[data-test="deal-disclosure"]').text()

    expect(text).toContain('Platform default')
    expect(text).toContain('Market default')
    expect(text).toContain('Derived from this parcel')
    expect(text).toContain('Your profile')
    expect(text).toContain('This scenario')
    expect(text).toContain('Source-reported')
  })

  it('(2) shows each assumption name and value', () => {
    const text = render(deal()).find('[data-test="deal-disclosure"]').text()

    expect(text).toContain('construction cost per sqft')
    expect(text).toContain('175')
    expect(text).toContain('Unavailable')
  })

  it('(3) keeps the unavailable-inputs sentence with its named inputs', () => {
    const text = render(deal()).find('[data-test="unavailable-inputs"]').text()

    expect(text).toContain('1 input is unavailable')
    expect(text).toContain('interest rate')
  })

  it('(3) pluralises the unavailable-inputs sentence', () => {
    const two = analysis({
      assumptions: [
        ...analysis().assumptions,
        {
          name: 'carry_months',
          group: 'financing_and_time',
          value: null,
          origin: 'platform_default',
          unit: 'months',
          limitations: null,
        },
      ],
    })

    expect(render(deal(), two).find('[data-test="unavailable-inputs"]').text()).toContain(
      '2 inputs are unavailable',
    )
  })

  it('(4) keeps the MAO exclusions and the formula', () => {
    const text = render(deal()).find('[data-test="deal-disclosure"]').text()

    expect(text).toContain('Not accounted for:')
    expect(text).toContain('financing interest, points, and loan fees')
    expect(text).toContain('carrying costs')
    expect(text).toContain('max_allowable_offer = (exit_value x (1 - selling_costs)) - costs')
  })

  it('(5) keeps the assumptions-source line verbatim', () => {
    expect(render(deal()).text()).toContain('Assumptions:')
    expect(render(deal()).text()).toContain('market default')
    expect(render(deal({ assumptions_source: 'calibrated' })).text()).toContain(
      'calibrated for this market',
    )
  })
})

describe('DealCard — structure and controls', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the downside/base/upside strip', () => {
    const wrapper = render(deal())

    expect(wrapper.find('[data-test="case-strip"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="case-mao-downside"]').text()).toBe('$90,000')
    expect(wrapper.find('[data-test="case-mao-base"]').text()).toBe('$145,000')
    expect(wrapper.find('[data-test="case-mao-upside"]').text()).toBe('$190,000')
  })

  it('mounts the sensitivity grid', () => {
    expect(render(deal()).find('[data-test="heatmap"]').exists()).toBe(true)
  })

  it('offers all three assumption controls without an expansion', () => {
    const labels = render(deal())
      .findAll('[data-test="deal-controls"] label')
      .map((l) => l.text())
      .join(' ')

    expect(labels).toContain('Acquisition price ($)')
    expect(labels).toContain('Target margin (%)')
    expect(labels).toContain('Construction ($/sqft)')
  })

  it('clamps inputs to the API bounds so a value cannot round-trip to a 422', () => {
    const wrapper = render(deal())
    const inputs = wrapper.findAll('[data-test="deal-controls"] input')
    const margin = inputs.find((i) => i.attributes('max') === '99')
    const cost = inputs.find((i) => i.attributes('max') === '2000')

    expect(margin).toBeTruthy()
    expect(cost).toBeTruthy()
    expect(cost?.attributes('min')).toBe('1')
  })

  it('labels the offer button so it signals a PDF', () => {
    expect(render(deal()).find('[data-test="deal-generate-offer"]').text()).toContain(
      'Generate offer (PDF)',
    )
  })

  it('shows a skeleton rather than a blank flash while loading', () => {
    setActivePinia(createPinia())
    const store = useParcelStore()
    store.detail = { parcel_number: 'phl:000000001' } as ParcelDetail
    store.deal = null
    store.dealLoading = true
    const wrapper = mount(DealCard, { global: { plugins: [Quasar] } })

    expect(wrapper.find('[data-test="deal-skeleton"]').exists()).toBe(true)
  })

  it('explains itself when there is no deal to model', () => {
    expect(render(null, null).text()).toContain('Not enough zoning or comparable-sales data')
  })

  it('seeds the offer letter from the max allowable offer the hero states', () => {
    const dialog = render(deal()).findComponent({ name: 'GenerateOfferDialog' })

    expect(dialog.props('maxAllowableOffer')).toBe(145000)
  })

  it('refuses to seed an offer letter on a deal that cannot clear its costs', () => {
    const dialog = render(deal({ infeasible: true })).findComponent({
      name: 'GenerateOfferDialog',
    })

    expect(dialog.props('maxAllowableOffer')).toBeNull()
  })
})
