import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import MobileTabBar from '@/components/MobileTabBar.vue'
import { routes } from '@/router'

function makeRouter(): Router {
  return createRouter({ history: createMemoryHistory(), routes })
}

async function mountBar(router: Router) {
  const wrapper = mount(MobileTabBar, { global: { plugins: [router, [Quasar, {}]] } })
  await router.isReady()
  return wrapper
}

describe('MobileTabBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the four primary tabs with market-scoped links', async () => {
    const router = makeRouter()
    const wrapper = await mountBar(router)
    const html = wrapper.html()
    expect(html).toContain('href="/philadelphia/home"')
    expect(html).toContain('href="/philadelphia/explore"')
    expect(html).toContain('href="/philadelphia/leads"')
    expect(wrapper.text()).toContain('More')
  })

  it('marks the active tab from the current route', async () => {
    const router = makeRouter()
    await router.push({ name: 'explore', params: { market: 'philadelphia' } })
    const wrapper = await mountBar(router)
    expect(wrapper.find('.tab.active').text()).toContain('Explore')
  })

  it('emits "more" when the More tab is tapped', async () => {
    const router = makeRouter()
    const wrapper = await mountBar(router)
    const more = wrapper.findAll('.tab').find((t) => t.text().includes('More'))
    await more?.trigger('click')
    expect(wrapper.emitted('more')).toHaveLength(1)
  })
})
