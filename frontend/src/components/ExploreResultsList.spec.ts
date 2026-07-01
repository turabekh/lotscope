import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import ExploreResultsList from '@/components/ExploreResultsList.vue'
import type { SpatialParcelResult } from '@/lib/types'

function result(overrides: Partial<SpatialParcelResult>): SpatialParcelResult {
  return {
    parcel_number: '001',
    address: '1 Main St',
    owner: null,
    base_zoning_code: 'RSA5',
    is_vacant: true,
    market_value: 100000,
    opportunity_score: 80,
    lng: null,
    lat: null,
    distance_m: null,
    ...overrides,
  }
}

function mountList(props: {
  results: SpatialParcelResult[]
  selectedParcel: string | null
  loading: boolean
}) {
  return mount(ExploreResultsList, { props, global: { plugins: [[Quasar, {}]] } })
}

const results = [
  result({ parcel_number: '001', address: '1 Main St', opportunity_score: 80 }),
  result({ parcel_number: '002', address: '2 Oak Ave', opportunity_score: 55 }),
]

describe('ExploreResultsList', () => {
  it('renders a row per result', () => {
    const wrapper = mountList({ results, selectedParcel: null, loading: false })
    expect(wrapper.findAll('.row')).toHaveLength(2)
    expect(wrapper.text()).toContain('1 Main St')
    expect(wrapper.text()).toContain('2 Oak Ave')
  })

  it('marks the row matching selectedParcel active (pin -> row)', () => {
    const wrapper = mountList({ results, selectedParcel: '002', loading: false })
    const active = wrapper.findAll('.row').filter((row) => row.classes().includes('active'))
    expect(active).toHaveLength(1)
    expect(active[0].attributes('data-parcel')).toBe('002')
  })

  it('emits select with the parcel number on row click (row -> pin)', async () => {
    const wrapper = mountList({ results, selectedParcel: null, loading: false })
    await wrapper.get('[data-parcel="001"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['001'])
  })

  it('shows the empty state when there are no results', () => {
    const wrapper = mountList({ results: [], selectedParcel: null, loading: false })
    expect(wrapper.text()).toContain('No lots listed yet')
    expect(wrapper.findAll('.row')).toHaveLength(0)
  })
})
