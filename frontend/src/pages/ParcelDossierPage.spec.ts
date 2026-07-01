import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ParcelDossierPage from '@/pages/ParcelDossierPage.vue'
import { useParcelStore } from '@/stores/parcel'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/parcel/:market/:id', name: 'parcel', component: ParcelDossierPage }],
  })
}

describe('ParcelDossierPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('fetches the parcel from the route id and renders the dossier standalone', async () => {
    const store = useParcelStore()
    const selectSpy = vi.spyOn(store, 'select').mockResolvedValue()
    const router = makeRouter()
    await router.push('/parcel/philadelphia/000012345')
    await router.isReady()

    const wrapper = mount(ParcelDossierPage, {
      global: { plugins: [router, [Quasar, {}]], stubs: { ParcelDossier: true } },
    })

    expect(selectSpy).toHaveBeenCalledWith('000012345')
    expect(wrapper.find('.dossier-frame').exists()).toBe(true)
  })
})
