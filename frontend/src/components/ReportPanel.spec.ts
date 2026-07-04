import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ReportPanel from '@/components/ReportPanel.vue'
import type { User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/account', name: 'account', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
}

function makeUser(tier: string): User {
  return {
    id: 1,
    email: 'a@b.co',
    full_name: null,
    role: 'user',
    tier,
    is_active: true,
    subscription_status: null,
    digest_frequency: 'weekly',
    created_at: '',
  }
}

function mountPanel() {
  const router = makeRouter()
  return mount(ReportPanel, {
    props: { parcelNumber: '000012345' },
    global: { plugins: [router, [Quasar, {}]] },
  })
}

function signIn(tier: string): void {
  const auth = useAuthStore()
  auth.token = 'tok'
  auth.user = makeUser(tier)
}

describe('ReportPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('shows the sign-in gate when unauthenticated', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('.signin-gate').exists()).toBe(true)
    expect(wrapper.find('.upgrade-gate').exists()).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().includes('Draft report'))).toBe(false)
  })

  it('shows the upgrade CTA for an authenticated free-tier user', async () => {
    signIn('free')
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.upgrade-gate').exists()).toBe(true)
    expect(wrapper.find('.signin-gate').exists()).toBe(false)
    expect(wrapper.text()).toContain('Upgrade to Pro')
    expect(wrapper.text()).not.toContain('Draft report')
  })

  it('shows the draft flow for a Pro-tier user', async () => {
    signIn('pro')
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.upgrade-gate').exists()).toBe(false)
    expect(wrapper.find('.signin-gate').exists()).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().includes('Draft report'))).toBe(true)
  })
})
