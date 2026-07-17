import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import App from '@/App.vue'
import { marketGuard, routes } from '@/router'
import { useAuthStore } from '@/stores/auth'

const getMe = vi.fn()
const getMarkets = vi.fn(() => Promise.resolve([]))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getMe: () => getMe(),
      getMarkets: () => getMarkets(),
    },
  }
})

function makeRouter(): Router {
  const router = createRouter({ history: createMemoryHistory(), routes })
  router.beforeEach(marketGuard)
  return router
}

function mountApp(router: Router) {
  return mount(App, {
    global: {
      plugins: [router, Quasar],
      stubs: {
        AppShell: { template: '<div class="shell-stub"><slot /></div>' },
        RouterView: true,
      },
    },
  })
}

describe('App auth boot gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    })
  })

  it('does not mount a gated route until the restored user has resolved', async () => {
    let resolveMe: (user: unknown) => void = () => {}
    getMe.mockReturnValue(
      new Promise((resolve) => {
        resolveMe = resolve
      }),
    )
    useAuthStore().token = 'test-token'

    const router = makeRouter()
    await router.push('/philadelphia/sheriff-sales')
    await router.isReady()

    const wrapper = mountApp(router)
    await flushPromises()

    expect(wrapper.find('router-view-stub').exists()).toBe(false)

    resolveMe({ id: 1, email: 'a@b.c', tier: 'pro', role: 'user' })
    await flushPromises()

    expect(wrapper.find('router-view-stub').exists()).toBe(true)
  })

  it('mounts a public route without waiting on the auth restore', async () => {
    const router = makeRouter()
    await router.push('/login')
    await router.isReady()

    const wrapper = mountApp(router)

    expect(wrapper.find('router-view-stub').exists()).toBe(true)
    expect(getMe).not.toHaveBeenCalled()
  })
})
