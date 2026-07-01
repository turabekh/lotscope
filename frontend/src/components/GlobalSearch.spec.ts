import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import GlobalSearch from '@/components/GlobalSearch.vue'
import SearchBox from '@/components/SearchBox.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/parcel/:market/:id', name: 'parcel', component: { template: '<div />' } }],
  })
}

describe('GlobalSearch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('navigates to the parcel dossier route on select', () => {
    const router = makeRouter()
    const push = vi.spyOn(router, 'push')
    const wrapper = mount(GlobalSearch, { global: { plugins: [router, [Quasar, {}]] } })

    wrapper.findComponent(SearchBox).vm.$emit('select', '000012345')

    expect(push).toHaveBeenCalledWith({
      name: 'parcel',
      params: { market: 'philadelphia', id: '000012345' },
    })
  })
})
