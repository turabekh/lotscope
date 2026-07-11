import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ReportPanel from '@/components/ReportPanel.vue'
import { api } from '@/lib/api'
import type { ParcelReportResult, User } from '@/lib/types'
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
    onboarded_at: null,
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

function makeReport(parcel: string): ParcelReportResult {
  return {
    parcel_number: parcel,
    headline: `Report for ${parcel}`,
    sections: [],
    recommendation: '',
    confidence: 'high',
    is_informational: true,
    sources: [],
    computed_at: '2026-07-05T00:00:00Z',
  }
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

  afterEach(() => vi.restoreAllMocks())

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

  it('discards a stale report draft after the parcel changed mid-flight', async () => {
    signIn('pro')
    let resolveSlow: (value: ParcelReportResult) => void = () => {}
    vi.spyOn(api, 'getParcelReport').mockImplementation((parcel: string) => {
      if (parcel === '000012345') {
        return new Promise<ParcelReportResult>((resolve) => {
          resolveSlow = resolve
        })
      }
      return Promise.resolve(makeReport(parcel))
    })

    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()

    const draftBtn = wrapper.findAll('button').find((b) => b.text().includes('Draft report'))
    await draftBtn?.trigger('click')

    await wrapper.setProps({ parcelNumber: '999999999' })
    await flushPromises()

    resolveSlow(makeReport('000012345'))
    await flushPromises()

    expect(wrapper.find('.report-headline').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Report for 000012345')
  })
})
