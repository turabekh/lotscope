import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Notify, Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GenerateOfferDialog from '@/components/GenerateOfferDialog.vue'
import type { OfferRequest, User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const { generateOfferMock } = vi.hoisted(() => ({
  generateOfferMock: vi.fn<(parcel: string, payload: unknown) => Promise<void>>(() =>
    Promise.resolve(),
  ),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, api: { ...actual.api, generateOffer: generateOfferMock } }
})

function mountDialog(tier: string, mao: number | null) {
  useAuthStore().user = {
    id: 1,
    email: 'a@example.com',
    full_name: 'Ada',
    tier,
    entity_name: 'ACME LLC',
  } as User
  return mount(GenerateOfferDialog, {
    props: { modelValue: true, parcelNumber: 'phl:1', maxAllowableOffer: mao },
    global: {
      plugins: [[Quasar, { plugins: { Notify } }]],
      stubs: { QDialog: { template: '<div><slot /></div>' } },
    },
  })
}

describe('GenerateOfferDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    generateOfferMock.mockClear()
  })

  it('prefills the offer price from the MAO and submits it', async () => {
    const wrapper = mountDialog('pro', 100000)
    await flushPromises()
    const priceInput = wrapper.find('input[type="number"]')
    expect((priceInput.element as HTMLInputElement).value).toBe('100000')

    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('Download LOI'))!
      .trigger('click')
    await flushPromises()
    expect(generateOfferMock).toHaveBeenCalled()
    const payload = generateOfferMock.mock.calls[0][1] as OfferRequest
    expect(payload.offer_price).toBe(100000)
    expect(payload.entity_name).toBe('ACME LLC')
  })

  it('sends an overridden price', async () => {
    const wrapper = mountDialog('investor', 100000)
    await flushPromises()
    await wrapper.find('input[type="number"]').setValue(85000)
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('Download LOI'))!
      .trigger('click')
    await flushPromises()
    const payload = generateOfferMock.mock.calls[0][1] as OfferRequest
    expect(payload.offer_price).toBe(85000)
  })

  it('shows the two-path banner and blocks submit when no economics and no price', async () => {
    const wrapper = mountDialog('pro', null)
    await flushPromises()
    expect(wrapper.text()).toContain('Compute the verdict first')
    const submit = wrapper.findAll('button').find((b) => b.text().includes('Download LOI'))!
    expect(submit.attributes('disabled')).toBeDefined()
    expect(generateOfferMock).not.toHaveBeenCalled()
  })
})
