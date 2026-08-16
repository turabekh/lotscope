import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FreshnessPanel from '@/components/FreshnessPanel.vue'
import { api } from '@/lib/api'
import type { SourceFreshness } from '@/lib/types'

function source(overrides: Partial<SourceFreshness> = {}): SourceFreshness {
  return {
    source_label: 'opa_properties_public',
    title: 'Assessment',
    as_of: '2026-06-27T00:00:00Z',
    datasets: ['opa_properties_public'],
    freshness: 'red',
    freshness_reason: 'Stale — last success 49 days ago (expected daily).',
    ...overrides,
  }
}

async function mountPanel(rows: SourceFreshness[]) {
  vi.spyOn(api, 'getParcelFreshness').mockResolvedValue(rows)
  const wrapper = mount(FreshnessPanel, {
    props: { parcelNumber: 'phl:000000001' },
    global: { plugins: [Quasar] },
  })
  await new Promise((resolve) => setTimeout(resolve, 0))
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('FreshnessPanel', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('says a stale source is stale rather than only how old it is', async () => {
    const wrapper = await mountPanel([source()])

    const flag = wrapper.find('[data-test="freshness-flag-opa_properties_public"]')
    expect(flag.exists()).toBe(true)
    expect(flag.text()).toBe('stale')
    expect(wrapper.text()).toContain('days ago')
  })

  it('flags an overdue source distinctly from a stale one', async () => {
    const wrapper = await mountPanel([
      source({ freshness: 'amber', freshness_reason: 'Overdue — last success 2 days ago.' }),
    ])

    expect(wrapper.find('[data-test="freshness-flag-opa_properties_public"]').text()).toBe(
      'overdue',
    )
  })

  it('adds no flag when every source is current', async () => {
    const wrapper = await mountPanel([
      source({ freshness: 'green', freshness_reason: 'Fresh — last success today.' }),
    ])

    expect(wrapper.find('[data-test="freshness-flag-opa_properties_public"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="freshness-behind"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('1/1 loaded')
  })

  it('summarises how many sources are behind schedule', async () => {
    const wrapper = await mountPanel([
      source(),
      source({ source_label: 'rtt_summary', title: 'Recorded sales', freshness: 'amber' }),
      source({ source_label: 'streets', title: 'Street access', freshness: 'green' }),
    ])

    expect(wrapper.find('[data-test="freshness-behind"]').text()).toContain('2 behind schedule')
  })
})
