import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import SensitivityHeatmap from '@/components/SensitivityHeatmap.vue'
import type { SensitivityCell, SensitivityGrid } from '@/lib/types'

const EXITS = [0.85, 0.925, 1.0, 1.075, 1.15]
const COSTS = [0.9, 0.95, 1.0, 1.05, 1.1]

function cell(exit: number, cost: number, over: Partial<SensitivityCell> = {}): SensitivityCell {
  return {
    exit_multiplier: exit,
    cost_multiplier: cost,
    margin: 0.25,
    profit: 100000,
    infeasible: false,
    ...over,
  }
}

function grid(over: Partial<SensitivityGrid> = {}): SensitivityGrid {
  return {
    available: true,
    unavailable_reason: null,
    row_label: 'Finished value',
    column_label: 'Construction cost',
    exit_multipliers: EXITS,
    cost_multipliers: COSTS,
    cells: EXITS.flatMap((e) => COSTS.map((c) => cell(e, c))),
    ...over,
  }
}

function render(value: SensitivityGrid | null) {
  return mount(SensitivityHeatmap, { props: { grid: value }, global: { plugins: [Quasar] } })
}

describe('SensitivityHeatmap', () => {
  it('renders a full five by five grid', () => {
    const wrapper = render(grid())

    expect(wrapper.find('[data-test="heatmap"]').exists()).toBe(true)
    expect(wrapper.findAll('tbody tr')).toHaveLength(5)
    expect(wrapper.findAll('tbody td')).toHaveLength(25)
  })

  it('marks the modelled base case', () => {
    const wrapper = render(grid())

    expect(wrapper.findAll('td.is-base')).toHaveLength(1)
  })

  it('renders infeasible cells as dead rather than as a margin', () => {
    const cells = EXITS.flatMap((e) =>
      COSTS.map((c) =>
        e === 0.85 ? cell(e, c, { infeasible: true, margin: null, profit: null }) : cell(e, c),
      ),
    )

    const wrapper = render(grid({ cells }))

    expect(wrapper.findAll('td.tone-dead')).toHaveLength(5)
    expect(wrapper.findAll('td.tone-dead')[0].text()).toBe('—')
  })

  it('colours by margin band', () => {
    const cells = [
      cell(0.85, 0.9, { margin: 0.3 }),
      cell(0.85, 0.95, { margin: 0.15 }),
      cell(0.85, 1.0, { margin: 0.05 }),
      cell(0.85, 1.05, { margin: -0.2 }),
      cell(0.85, 1.1, { margin: null }),
    ]

    const wrapper = render(grid({ exit_multipliers: [0.85], cost_multipliers: COSTS, cells }))

    const classes = wrapper.findAll('tbody td').map((td) => td.classes().join(' '))
    expect(classes[0]).toContain('tone-strong')
    expect(classes[1]).toContain('tone-fair')
    expect(classes[2]).toContain('tone-thin')
    expect(classes[3]).toContain('tone-loss')
    expect(classes[4]).toContain('tone-missing')
  })

  it('shows the honest reason instead of an empty grid', () => {
    const wrapper = render(
      grid({
        available: false,
        unavailable_reason: 'No comparable finished sales were available.',
        cells: [],
      }),
    )

    expect(wrapper.find('[data-test="heatmap-unavailable"]').text()).toContain(
      'No comparable finished sales',
    )
    expect(wrapper.find('[data-test="heatmap"]').exists()).toBe(false)
  })

  it('renders nothing at all without a grid', () => {
    expect(render(null).text()).toBe('')
  })
})
