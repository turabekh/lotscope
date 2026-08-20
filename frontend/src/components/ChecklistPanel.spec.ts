import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import ChecklistPanel from '@/components/ChecklistPanel.vue'
import type { ChecklistItem, ChecklistStatus } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function item(code: string, status: ChecklistStatus, detail: string, label = code): ChecklistItem {
  return { code, label, category: code, status, detail, source: null, availability: 'available' }
}

function mountPanel(items: ChecklistItem[]) {
  const store = useParcelStore()
  store.checklist = {
    parcel_number: 'phl:1',
    items,
    posture: null,
    summary: {
      passed: items.filter((i) => i.status === 'pass').length,
      warnings: items.filter((i) => i.status === 'potential_issue').length,
      failures: items.filter((i) => i.status === 'fail').length,
      info: 0,
      not_evaluated: items.filter((i) => i.status === 'not_evaluated').length,
      ready: !items.some((i) => i.status === 'fail'),
    },
    buildability_confidence: 'high',
    buildability_confidence_reasons: [],
    program: null,
    computed_at: '2026-07-28T00:00:00Z',
  }
  return mount(ChecklistPanel, { global: { plugins: [[Quasar, {}]] } })
}

describe('ChecklistPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('tells the user how many checks were not performed', () => {
    const wrapper = mountPanel([
      item('zoning', 'pass', 'Base district resolved.'),
      item('access', 'not_evaluated', 'No street centerline loaded for this market.'),
    ])
    expect(wrapper.text()).toContain('1 clear')
    expect(wrapper.text()).toContain('1 not checked')
  })

  it('calls failed conformance checks blocking items, not deal killers', () => {
    const wrapper = mountPanel([
      item('lot_area', 'fail', 'Lot is 884 sqft against a 1440 sqft minimum.'),
      item('lot_width', 'fail', 'Lot is 14 ft wide against a 16 ft minimum.'),
    ])
    expect(wrapper.text()).toContain('2 blocking item(s) to clear')
    expect(wrapper.text().toLowerCase()).not.toContain('deal-killer')
    expect(wrapper.text().toLowerCase()).not.toContain('deal killer')
  })

  it('states why an unevaluated check was not performed', () => {
    const wrapper = mountPanel([
      item('li', 'not_evaluated', 'This market publishes no code-enforcement feed.'),
    ])
    expect(wrapper.text()).toContain('publishes no code-enforcement feed')
  })

  it('does not render an unevaluated check with the passing icon', () => {
    const passing = mountPanel([item('zoning', 'pass', 'Resolved.')]).html()
    const unevaluated = mountPanel([item('zoning', 'not_evaluated', 'Not loaded.')]).html()
    expect(passing).toContain('check_circle')
    expect(unevaluated).not.toContain('check_circle')
  })

  it('omits the not-checked count entirely when everything was evaluated', () => {
    const wrapper = mountPanel([item('zoning', 'pass', 'Resolved.')])
    expect(wrapper.text()).not.toContain('not checked')
  })

  it('names each check rather than repeating its category', () => {
    const wrapper = mountPanel([
      item('min_lot_area', 'not_evaluated', 'No minimum lot area.', 'Minimum lot area'),
      item('max_height', 'not_evaluated', 'No maximum height.', 'Maximum height'),
      item('unit_density', 'not_evaluated', 'No density limit.', 'Unit density'),
    ])
    const labels = wrapper.findAll('[data-test="check-label"]').map((node) => node.text())

    expect(labels).toEqual(['Minimum lot area', 'Maximum height', 'Unit density'])
    expect(new Set(labels).size).toBe(labels.length)
  })
})
