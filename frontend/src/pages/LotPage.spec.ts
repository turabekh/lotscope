import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import LotPage from '@/pages/LotPage.vue'
import { useParcelStore } from '@/stores/parcel'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/lot/:parcelNumber', name: 'lot', component: LotPage }],
  })
}

describe('LotPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('fetches the parcel from the route parcel number and renders the dossier standalone', async () => {
    const store = useParcelStore()
    const selectSpy = vi.spyOn(store, 'select').mockResolvedValue()
    const router = makeRouter()
    await router.push('/lot/phl:000012345')
    await router.isReady()

    const wrapper = mount(LotPage, {
      global: {
        plugins: [router, [Quasar, {}]],
        stubs: { ParcelDossier: true, MapView: true },
      },
    })

    expect(selectSpy).toHaveBeenCalledWith('phl:000012345')
    expect(wrapper.find('.dossier-frame').exists()).toBe(true)
  })

  it('puts the map beside the dossier when there is room for it', async () => {
    const store = useParcelStore()
    vi.spyOn(store, 'select').mockResolvedValue()
    const router = makeRouter()
    await router.push('/lot/phl:000012345')
    await router.isReady()

    const wrapper = mount(LotPage, {
      global: {
        plugins: [router, [Quasar, {}]],
        stubs: { ParcelDossier: true, MapView: true },
      },
    })

    expect(wrapper.find('[data-test="dossier-map"]').exists()).toBe(true)
  })
})
