import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import DiscoverySources from '@/components/DiscoverySources.vue'
import { routes } from '@/router'

async function mountSources(): Promise<ReturnType<typeof mount>> {
  const router: Router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(DiscoverySources, {
    global: { plugins: [router, [Quasar, {}]] },
  })
  await router.isReady()
  return wrapper
}

describe('DiscoverySources', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('links the consolidated discovery surfaces', async () => {
    const html = (await mountSources()).html()
    expect(html).toContain('href="/feed"')
    expect(html).toContain('href="/sheriff-sales"')
    expect(html).toContain('href="/top-plays"')
  })
})
