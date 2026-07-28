import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OnboardingTour from '@/components/OnboardingTour.vue'
import type { User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const { markOnboardedMock } = vi.hoisted(() => ({
  markOnboardedMock: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, api: { ...actual.api, markOnboarded: markOnboardedMock } }
})

function makeUser(onboardedAt: string | null): User {
  return {
    id: 1,
    email: 'a@b.co',
    full_name: null,
    role: 'user',
    tier: 'free',
    is_active: true,
    subscription_status: null,
    digest_frequency: 'weekly',
    onboarded_at: onboardedAt,
    created_at: '',
  }
}

function mountTour() {
  return mount(OnboardingTour, { global: { plugins: [[Quasar, {}]] }, attachTo: document.body })
}

async function clickButton(label: string): Promise<void> {
  const button = [...document.body.querySelectorAll('button')].find(
    (element) => element.textContent?.trim() === label,
  )
  if (!button) throw new Error(`button "${label}" not found`)
  button.click()
  await flushPromises()
}

describe('OnboardingTour', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
    markOnboardedMock.mockClear()
  })

  it('does not show for an already-onboarded user', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.user = makeUser('2026-01-01T00:00:00Z')
    mountTour()
    await flushPromises()
    expect(document.body.textContent).not.toContain('Welcome to LotScope')
  })

  it('shows for a new user and completes on Skip', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.user = makeUser(null)
    mountTour()
    await flushPromises()
    expect(document.body.textContent).toContain('Welcome to LotScope')

    await clickButton('Skip')
    expect(markOnboardedMock).toHaveBeenCalledTimes(1)
  })

  it('advances through the slides and finishes on the last', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.user = makeUser(null)
    mountTour()
    await flushPromises()

    await clickButton('Next')
    await clickButton('Next')
    await clickButton('Next')
    await clickButton('Get started')
    expect(markOnboardedMock).toHaveBeenCalledTimes(1)
  })
})
