import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import AppSidebar from '@/components/AppSidebar.vue'
import { routes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/lib/types'

function makeRouter(): Router {
  return createRouter({ history: createMemoryHistory(), routes })
}

function setUser(role: 'user' | 'admin'): void {
  useAuthStore().user = { id: 1, email: 't@x.co', role, tier: 'free' } as unknown as User
}

async function mountSidebar(router: Router) {
  const wrapper = mount(AppSidebar, {
    props: { collapsed: false },
    global: { plugins: [router, [Quasar, {}]] },
  })
  await router.isReady()
  return wrapper
}

describe('AppSidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the nav links', async () => {
    setUser('user')
    const router = makeRouter()
    const wrapper = await mountSidebar(router)
    const html = wrapper.html()
    expect(html).toContain('href="/"')
    expect(html).toContain('href="/deals"')
    expect(html).toContain('href="/packets"')
    expect(html).toContain('href="/account"')
  })

  it('marks the active section from the current route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'deals' })
    const wrapper = await mountSidebar(router)
    expect(wrapper.find('.nav-active').text()).toContain('Deals')
  })

  it('hides Admin for non-admins and shows it for admins', async () => {
    const router = makeRouter()

    setUser('user')
    const asUser = await mountSidebar(router)
    expect(asUser.text()).not.toContain('Admin')

    setUser('admin')
    const asAdmin = await mountSidebar(router)
    expect(asAdmin.text()).toContain('Admin')
  })

  it('keeps primary navigation to three destinations', async () => {
    setUser('user')
    const wrapper = await mountSidebar(makeRouter())
    const primary = wrapper.findAll('[data-test="nav-primary"] > .nav-item')
    expect(primary).toHaveLength(3)
    const labels = primary.map((item) => item.text())
    ;['Analyst', 'Deals', 'Packets'].forEach((label, index) => {
      expect(labels[index]).toContain(label)
    })
  })

  it('offers no route Phase 3 deleted', async () => {
    setUser('user')
    const html = (await mountSidebar(makeRouter())).html()
    for (const gone of [
      '/explore',
      '/feed',
      '/leads',
      '/lists',
      '/top-plays',
      '/buyers',
      '/market',
      '/sheriff-sales',
    ]) {
      expect(html).not.toContain(`href="${gone}"`)
    }
  })
})
