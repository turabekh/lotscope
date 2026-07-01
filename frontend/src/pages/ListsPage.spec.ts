import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ListsPage from '@/pages/ListsPage.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:market/lists', name: 'lists', component: ListsPage }],
  })
}

async function mountAt(query: string) {
  const router = makeRouter()
  await router.push(`/philadelphia/lists${query}`)
  await router.isReady()
  return mount(ListsPage, {
    global: {
      plugins: [router, [Quasar, {}]],
      stubs: { SavedLotsList: true, SavedSearchesList: true },
    },
  })
}

describe('ListsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('activates the Saved lots tab by default', async () => {
    const wrapper = await mountAt('')
    expect(wrapper.find('.q-tab--active').text()).toContain('Saved lots')
  })

  it('activates the Saved searches tab when ?tab=searches', async () => {
    const wrapper = await mountAt('?tab=searches')
    expect(wrapper.find('.q-tab--active').text()).toContain('Saved searches')
  })
})
