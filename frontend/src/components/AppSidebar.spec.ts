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
    expect(html).toContain('href="/home"')
    expect(html).toContain('href="/explore"')
    expect(html).toContain('href="/leads"')
    expect(html).toContain('href="/lists"')
    expect(html).toContain('href="/account"')
  })

  it('marks the active section from the current route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'leads' })
    const wrapper = await mountSidebar(router)
    expect(wrapper.find('.nav-active').text()).toContain('Leads')
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

  it('keeps primary navigation to five destinations', async () => {
    setUser('user')
    const wrapper = await mountSidebar(makeRouter())
    const primary = wrapper.findAll('[data-test="nav-primary"] > .nav-item')
    expect(primary).toHaveLength(5)
    const labels = primary.map((item) => item.text())
    ;['Home', 'Find lots', 'Leads', 'Pipeline', 'Lists'].forEach((label, index) => {
      expect(labels[index]).toContain(label)
    })
  })

  it('keeps the consolidated surfaces reachable under Research', async () => {
    setUser('user')
    const wrapper = await mountSidebar(makeRouter())
    const research = wrapper.find('[data-test="nav-research"]')
    expect(research.exists()).toBe(true)
    const html = research.html()
    expect(html).toContain('href="/feed"')
    expect(html).toContain('href="/sheriff-sales"')
    expect(html).toContain('href="/top-plays"')
    expect(html).toContain('href="/buyers"')
    expect(html).toContain('href="/market"')
  })

  it('opens Research when one of its surfaces is the active route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'buyers' })
    const wrapper = await mountSidebar(router)
    expect(wrapper.find('.nav-active').text()).toContain('Cash buyers')
  })
})
