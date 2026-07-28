import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import BuyBoxOnboarding from '@/components/BuyBoxOnboarding.vue'
import { api } from '@/lib/api'
import { routes } from '@/router'
import type { BuyBoxMatches, UnderwritingProfile } from '@/lib/types'

function matches(overrides: Partial<BuyBoxMatches> = {}): BuyBoxMatches {
  return {
    market: 'phl',
    total: 0,
    matches: [],
    criteria_applied: ['max_acquisition_price'],
    has_profile: true,
    ...overrides,
  }
}

async function mountOnboarding() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(BuyBoxOnboarding, { global: { plugins: [router, [Quasar, {}]] } })
  await router.isReady()
  return wrapper
}

describe('BuyBoxOnboarding', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('creates a default profile when the user has none', async () => {
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    const create = vi
      .spyOn(api, 'createUnderwritingProfile')
      .mockResolvedValue({} as UnderwritingProfile)
    vi.spyOn(api, 'getBuyBoxMatches').mockResolvedValue(matches())

    const wrapper = await mountOnboarding()
    await wrapper.find('input[data-test="buy-box-price"]').setValue('150000')
    await wrapper.find('[data-test="buy-box-submit"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledOnce()
    const payload = create.mock.calls[0]![0]
    expect(payload.is_default).toBe(true)
    expect(payload.buy_box.max_acquisition_price).toBe(150000)
  })

  it('converts a percentage margin into a fraction', async () => {
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    const create = vi
      .spyOn(api, 'createUnderwritingProfile')
      .mockResolvedValue({} as UnderwritingProfile)
    vi.spyOn(api, 'getBuyBoxMatches').mockResolvedValue(matches())

    const wrapper = await mountOnboarding()
    await wrapper.find('input[data-test="buy-box-margin"]').setValue('25')
    await wrapper.find('[data-test="buy-box-submit"]').trigger('click')
    await flushPromises()

    expect(create.mock.calls[0]![0].buy_box.min_margin).toBe(0.25)
  })

  it('updates the existing default profile rather than creating a second', async () => {
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([
      { id: 7, name: 'Mine', is_default: true, assumptions: {}, buy_box: {} },
    ] as UnderwritingProfile[])
    const update = vi
      .spyOn(api, 'updateUnderwritingProfile')
      .mockResolvedValue({} as UnderwritingProfile)
    const create = vi.spyOn(api, 'createUnderwritingProfile')
    vi.spyOn(api, 'getBuyBoxMatches').mockResolvedValue(matches())

    const wrapper = await mountOnboarding()
    await wrapper.find('input[data-test="buy-box-units"]').setValue('2')
    await wrapper.find('[data-test="buy-box-submit"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledOnce()
    expect(update.mock.calls[0]![0]).toBe(7)
    expect(create).not.toHaveBeenCalled()
  })

  it('states that uncalculated lots are never counted when nothing matches', async () => {
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    vi.spyOn(api, 'createUnderwritingProfile').mockResolvedValue({} as UnderwritingProfile)
    vi.spyOn(api, 'getBuyBoxMatches').mockResolvedValue(matches({ total: 0 }))

    const wrapper = await mountOnboarding()
    await wrapper.find('input[data-test="buy-box-price"]').setValue('1000')
    await wrapper.find('[data-test="buy-box-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="buy-box-results"]').text()).toContain(
      'never counted as matches',
    )
  })

  it('reports a save failure without claiming anything changed', async () => {
    vi.spyOn(api, 'listUnderwritingProfiles').mockRejectedValue(new Error('nope'))

    const wrapper = await mountOnboarding()
    await wrapper.find('input[data-test="buy-box-price"]').setValue('150000')
    await wrapper.find('[data-test="buy-box-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="buy-box-error"]').text()).toContain('Nothing was changed')
    expect(wrapper.find('[data-test="buy-box-results"]').exists()).toBe(false)
  })
})
