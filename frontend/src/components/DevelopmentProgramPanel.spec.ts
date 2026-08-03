import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DevelopmentProgramPanel from '@/components/DevelopmentProgramPanel.vue'
import type { DevelopmentProgram, ParcelChecklist } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function makeProgram(overrides: Partial<DevelopmentProgram> = {}): DevelopmentProgram {
  return {
    statement:
      'On this 15,592 sq ft CMX-4 lot, multi-family and commercial uses are permitted by right.',
    claims: [
      { label: 'Base district', value: 'CMX-4', state: 'verified' },
      { label: 'Buildable footprint', value: '11,800 sq ft', state: 'calculated' },
      { label: 'By-right units', value: 'not determined', state: 'unavailable' },
    ],
    citation: 'CMX-4 (Title 14, title14-quickguide-2026-02)',
    conditions: ['Informational only, not a zoning determination.'],
    ...overrides,
  }
}

function mountPanel(program: DevelopmentProgram | null) {
  const store = useParcelStore()
  store.checklist = {
    parcel_number: 'phl:1',
    items: [],
    summary: { passed: 0, warnings: 0, failures: 0, info: 0, not_evaluated: 0, ready: true },
    buildability_confidence: 'high',
    buildability_confidence_reasons: [],
    program,
    computed_at: '2026-08-03T00:00:00Z',
  } as ParcelChecklist
  return mount(DevelopmentProgramPanel, {
    global: { plugins: [[Quasar, {}]], stubs: { QTooltip: true } },
  })
}

describe('DevelopmentProgramPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('states what can be built in prose the reader can act on', () => {
    const statement = mountPanel(makeProgram()).find('[data-test="program-statement"]')

    expect(statement.isVisible()).toBe(true)
    expect(statement.text()).toContain('multi-family and commercial uses are permitted by right')
  })

  it('cites the standard and its version', () => {
    const citation = mountPanel(makeProgram()).find('[data-test="program-citation"]')

    expect(citation.isVisible()).toBe(true)
    expect(citation.text()).toContain('title14-quickguide-2026-02')
  })

  it('labels every claim with how it was established', () => {
    const claims = mountPanel(makeProgram()).find('[data-test="program-claims"]')

    expect(claims.text()).toContain('verified')
    expect(claims.text()).toContain('calculated')
    expect(claims.text()).toContain('unavailable')
  })

  it('shows an unavailable claim as unavailable rather than as a zero', () => {
    const text = mountPanel(makeProgram()).find('[data-test="program-claims"]').text()

    expect(text).toContain('not determined')
    expect(text).not.toContain('0 units')
  })

  it('renders the conditions outside any tooltip', () => {
    const conditions = mountPanel(makeProgram()).find('[data-test="program-conditions"]')

    expect(conditions.isVisible()).toBe(true)
    expect(conditions.text()).toContain('not a zoning determination')
  })

  it('renders nothing when no program could be composed', () => {
    expect(mountPanel(null).find('[data-test="program-panel"]').exists()).toBe(false)
  })
})
