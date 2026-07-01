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

  it('renders scoped nav links carrying the active market', async () => {
    setUser('user')
    const router = makeRouter()
    const wrapper = await mountSidebar(router)
    const html = wrapper.html()
    expect(html).toContain('href="/philadelphia/home"')
    expect(html).toContain('href="/philadelphia/explore"')
    expect(html).toContain('href="/philadelphia/leads"')
    expect(html).toContain('href="/philadelphia/saved-searches"')
    expect(html).toContain('href="/account"')
  })

  it('marks the active section from the current route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'leads', params: { market: 'philadelphia' } })
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
})
