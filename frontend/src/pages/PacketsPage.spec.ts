import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import PacketsPage from '@/pages/PacketsPage.vue'

const PACKET = {
  id: 7,
  sale_date: '2026-09-16',
  status: 'ready' as const,
  error: null,
  generated_at: '2026-09-05T00:00:00Z',
  download_url: '/packets/7/download',
}

function mountPage() {
  return mount(PacketsPage, {
    global: {
      plugins: [Quasar],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
}

describe('PacketsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'getPackets').mockResolvedValue([PACKET])
  })

  it('offers the packet at its price when purchasing is on', async () => {
    vi.spyOn(api, 'getCheckoutPrices').mockResolvedValue({
      configured: true,
      skus: { packet: { amount_cents: 4900, label: 'Sale Packet' } },
    })

    const wrapper = mountPage()
    await flushPromises()

    const button = wrapper.find('[data-test="packet-buy"]')
    expect(button.exists()).toBe(true)
    expect(wrapper.text()).toContain('Get this packet — $49')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="packet-buy-soon"]').exists()).toBe(false)
  })

  it('disables the button and says so when purchasing is off', async () => {
    vi.spyOn(api, 'getCheckoutPrices').mockResolvedValue({
      configured: false,
      skus: { packet: { amount_cents: 4900, label: 'Sale Packet' } },
    })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-test="packet-buy"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="packet-buy-soon"]').text()).toBe('Purchasing opens soon')
  })
})
