import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import DealsPage from '@/pages/DealsPage.vue'
import type { DealItem } from '@/lib/types'
import { routes } from '@/router'
import { usePipelineStore } from '@/stores/pipeline'

vi.mock('@/lib/api', async (original) => {
  const actual = await original<typeof import('@/lib/api')>()
  return { ...actual, api: { ...actual.api, exportPipeline: vi.fn().mockResolvedValue(undefined) } }
})

function deal(overrides: Partial<DealItem> = {}): DealItem {
  return {
    id: 1,
    parcel_number: 'phl:463278700',
    address: '902 S CECIL ST',
    stage: 'lead',
    note: null,
    target_price: 21000,
    next_action: 'Check the title',
    next_action_due: '2026-09-12',
    stage_entered_at: null,
    contact_name: null,
    contact_phone: null,
    contact_email: null,
    base_zoning_code: 'RSA-5',
    is_vacant: true,
    market_value: 40000,
    opportunity_score: 71,
    max_allowable_offer: 24300,
    arv: null,
    est_profit: null,
    est_margin: null,
    is_underpriced: true,
    sale_date: '2026-09-16',
    agent_run_id: 20,
    analyst_note: 'BID grade on the 2026-09-16 packet — expected clearing $24,300.\nMore detail.',
    analyst_note_at: '2026-09-05T12:00:00Z',
    updated_at: '2026-09-05T12:00:00Z',
    ...overrides,
  } as DealItem
}

async function mountPage(items: DealItem[]) {
  setActivePinia(createPinia())
  const store = usePipelineStore()
  store.deals = items
  store.loaded = true
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/deals')
  await router.isReady()
  return mount(DealsPage, { global: { plugins: [router, [Quasar, {}]] } })
}

describe('DealsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('is a table with a row per deal', async () => {
    const wrapper = await mountPage([deal(), deal({ id: 2, parcel_number: 'phl:2' })])
    expect(wrapper.find('[data-test="deals-table"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-test="deals-row"]')).toHaveLength(2)
  })

  it('shows the offer beside what the lot is worth paying', async () => {
    const wrapper = await mountPage([deal()])
    expect(wrapper.find('[data-test="deals-mao"]').text()).toContain('24,300')
    expect(wrapper.find('[data-test="deals-offer"]').text()).toContain('21,000')
  })

  it('says when the lot sells, and says so plainly when it is not listed', async () => {
    const listed = await mountPage([deal()])
    expect(listed.find('[data-test="deals-sale"]').text()).toBe('2026-09-16')

    const unlisted = await mountPage([deal({ sale_date: null })])
    expect(unlisted.find('[data-test="deals-sale"]').text()).toBe('not listed')
  })

  it('carries the Analyst note from the run that put the row here, dated', async () => {
    const wrapper = await mountPage([deal()])
    const note = wrapper.find('[data-test="deals-note"]')
    expect(note.text()).toContain('BID grade on the 2026-09-16 packet')
    expect(note.text()).toContain('2026-09-05')
  })

  it('does not invent a note for a row a person added by hand', async () => {
    const wrapper = await mountPage([deal({ analyst_note: null, agent_run_id: null })])
    expect(wrapper.find('[data-test="deals-note"]').text()).toBe('added by hand')
  })

  it('saves a stage change without a second confirming click', async () => {
    const wrapper = await mountPage([deal()])
    const store = usePipelineStore()
    const move = vi.spyOn(store, 'moveStage').mockResolvedValue(undefined)

    const select = wrapper.find('[data-test="deals-stage"]')
    await select.setValue('diligence')

    expect(move).toHaveBeenCalledWith('phl:463278700', 'diligence')
  })

  it('will not ask about nothing', async () => {
    const wrapper = await mountPage([deal()])
    expect(wrapper.find('[data-test="deals-ask"]').attributes('disabled')).toBeDefined()
  })

  it('asks the Analyst about exactly what was selected', async () => {
    const wrapper = await mountPage([
      deal(),
      deal({ id: 2, parcel_number: 'phl:2', address: 'B ST' }),
    ])
    await wrapper.findAll('[data-test="deals-select"]')[1].trigger('change')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="deals-ask"]').text()).toContain('Ask about 1')
  })

  it('offers an export', async () => {
    const wrapper = await mountPage([deal()])
    expect(wrapper.find('[data-test="deals-export"]').exists()).toBe(true)
  })

  it('opens the offer letter for the row it was asked about', async () => {
    const wrapper = await mountPage([
      deal(),
      deal({ id: 2, parcel_number: 'phl:2', address: 'B ST', max_allowable_offer: 9000 }),
    ])
    await wrapper.findAll('[data-test="deals-offer-letter"]')[1].trigger('click')
    await wrapper.vm.$nextTick()

    const dialog = wrapper.findComponent({ name: 'GenerateOfferDialog' })
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('parcelNumber')).toBe('phl:2')
    expect(dialog.props('maxAllowableOffer')).toBe(9000)
  })

  it('says what an empty pipeline means rather than showing a bare table', async () => {
    const wrapper = await mountPage([])
    expect(wrapper.find('[data-test="deals-empty"]').text()).toContain('Ask the Analyst')
  })
})
