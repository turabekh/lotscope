import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import AnalystPage from '@/pages/AnalystPage.vue'
import { api } from '@/lib/api'
import { routes } from '@/router'
import { useAnalystStore } from '@/stores/analyst'

async function mountPage(width: number) {
  setActivePinia(createPinia())
  // Quasar's Screen plugin reads the real window, and jsdom's default is a desktop.
  window.innerWidth = width
  window.dispatchEvent(new Event('resize'))
  vi.spyOn(api, 'todaysBrief').mockResolvedValue(null)
  const analyst = useAnalystStore()
  vi.spyOn(analyst, 'loadConversations').mockResolvedValue()
  vi.spyOn(analyst, 'loadOpening').mockResolvedValue()

  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/')
  await router.isReady()

  return mount(AnalystPage, {
    global: {
      plugins: [router, [Quasar, {}]],
      stubs: { MessageThread: true, EvidenceDrawer: true, ConversationList: true },
    },
  })
}

describe('AnalystPage on a phone', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('keeps the conversations behind a toggle rather than on the screen', async () => {
    const wrapper = await mountPage(380)
    expect(wrapper.find('[data-test="analyst-rail-toggle"]').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ConversationList' }).exists()).toBe(false)
  })

  it('opens them as a sheet, and closes on a tap away from it', async () => {
    const wrapper = await mountPage(380)
    await wrapper.find('[data-test="analyst-rail-toggle"]').trigger('click')

    expect(wrapper.find('.analyst__rail--sheet').exists()).toBe(true)
    expect(wrapper.find('[data-test="analyst-rail-scrim"]').exists()).toBe(true)

    await wrapper.find('[data-test="analyst-rail-scrim"]').trigger('click')
    expect(wrapper.find('.analyst__rail--sheet').exists()).toBe(false)
  })
})
