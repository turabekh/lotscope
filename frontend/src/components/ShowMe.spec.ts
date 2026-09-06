import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it, vi } from 'vitest'

import ShowMe from '@/components/ShowMe.vue'
import {
  atlasUrl,
  cartoTarget,
  provisionTarget,
  storedTarget,
  violationTarget,
} from '@/lib/sourceLinks'

vi.mock('@/lib/api', () => ({
  api: {
    getProvision: vi.fn().mockResolvedValue({
      id: '14-701',
      cite: '§ 14-701',
      heading: 'Dimensional standards',
      text: 'The minimum lot area in RSA-5 is 1,440 square feet.',
      source_url: 'https://codelibrary.amlegal.com/x',
    }),
  },
}))

function showMe(target: ReturnType<typeof storedTarget>) {
  return mount(ShowMe, { props: { target }, global: { plugins: [[Quasar, {}]] } })
}

describe('source links', () => {
  it('builds an Atlas link from a prefixed parcel number', () => {
    expect(atlasUrl('phl:191357500')).toBe('https://atlas.phila.gov/191357500')
  })

  it('builds an L&I history link from the address', () => {
    const target = violationTarget('3862 ASPEN ST')
    expect(target.kind).toBe('external')
    if (target.kind !== 'external') throw new Error('expected external')
    expect(target.url).toContain('3862%20ASPEN%20ST')
  })

  it('falls back to the stored source when there is no address to search', () => {
    expect(violationTarget(null).kind).toBe('stored')
  })

  it('builds a Carto row query anyone can run', () => {
    const target = cartoTarget('opa_properties_public', 'phl:191357500')
    if (target.kind !== 'external') throw new Error('expected external')
    expect(decodeURIComponent(target.url)).toContain(
      "SELECT * FROM opa_properties_public WHERE parcel_number = '191357500'",
    )
  })
})

describe('ShowMe', () => {
  it('links straight out when the source has a public page', () => {
    const wrapper = showMe(cartoTarget('opa_properties_public', 'phl:1'))
    const link = wrapper.find('[data-test="show-me-external"]')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
  })

  it('says which of our sources said it when no public page exists', async () => {
    const wrapper = showMe(storedTarget('lotscope_verdict', '2026-09-05T04:12:00Z'))
    await wrapper.find('[data-test="show-me"]').trigger('click')

    const pop = wrapper.find('[data-test="show-me-stored"]')
    expect(pop.text()).toContain('lotscope_verdict')
    expect(pop.text()).toContain('as of 2026-09-05')
  })

  it('admits when it has no as-of rather than implying it is current', async () => {
    const wrapper = showMe(storedTarget('rtt_summary', null))
    await wrapper.find('[data-test="show-me"]').trigger('click')
    expect(wrapper.text()).toContain('no as-of recorded')
  })

  it('opens the Title 14 text behind a citation', async () => {
    const wrapper = showMe(provisionTarget('14-701', '§ 14-701'))
    await wrapper.find('[data-test="show-me"]').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    const pop = wrapper.find('[data-test="show-me-provision"]')
    expect(pop.text()).toContain('§ 14-701')
    expect(pop.text()).toContain('1,440 square feet')
  })

  it('announces whether it is open', () => {
    const wrapper = showMe(storedTarget('parcel', null))
    expect(wrapper.find('[data-test="show-me"]').attributes('aria-expanded')).toBe('false')
  })
})
