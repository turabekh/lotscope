import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/lib/api'
import type { DealItem } from '@/lib/types'
import { usePipelineStore } from '@/stores/pipeline'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ApiError: actual.ApiError,
    api: {
      getPipeline: vi.fn(),
      addToPipeline: vi.fn(),
      updateDeal: vi.fn(),
      getPipelineToday: vi.fn(),
      getDealActivity: vi.fn(),
      removeFromPipeline: vi.fn(),
    },
  }
})

function deal(partial: Partial<DealItem>): DealItem {
  return {
    id: 1,
    parcel_number: '001',
    stage: 'lead',
    note: null,
    target_price: null,
    next_action: null,
    next_action_due: null,
    stage_entered_at: null,
    contact_name: null,
    contact_phone: null,
    contact_email: null,
    address: '1 Main',
    base_zoning_code: null,
    is_vacant: null,
    market_value: null,
    opportunity_score: null,
    max_allowable_offer: null,
    arv: null,
    est_profit: null,
    est_margin: null,
    is_underpriced: null,
    updated_at: '2026-07-11T00:00:00Z',
    ...partial,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('pipeline store', () => {
  it('loads deals and limit', async () => {
    vi.mocked(api.getPipeline).mockResolvedValue({
      limit: 10,
      used: 1,
      deals: [deal({ id: 1 })],
    })
    const store = usePipelineStore()
    await store.load()
    expect(store.deals).toHaveLength(1)
    expect(store.limit).toBe(10)
    expect(store.atLimit).toBe(false)
  })

  it('moveStage is optimistic and rolls back on error', async () => {
    vi.mocked(api.getPipeline).mockResolvedValue({
      limit: null,
      used: 1,
      deals: [deal({ id: 1, stage: 'lead' })],
    })
    vi.mocked(api.updateDeal).mockRejectedValue(new ApiError(500, 'boom'))
    const store = usePipelineStore()
    await store.load()

    await expect(store.moveStage('001', 'offer')).rejects.toBeInstanceOf(ApiError)
    expect(store.dealFor('001')?.stage).toBe('lead')
  })

  it('loadToday populates the today list', async () => {
    vi.mocked(api.getPipelineToday).mockResolvedValue({
      deals: [deal({ id: 2, next_action_due: '2026-07-01' })],
    })
    const store = usePipelineStore()
    await store.loadToday()
    expect(store.today).toHaveLength(1)
    expect(store.today[0]!.next_action_due).toBe('2026-07-01')
  })

  it('updateDeal replaces the deal with the server copy', async () => {
    vi.mocked(api.getPipeline).mockResolvedValue({
      limit: null,
      used: 1,
      deals: [deal({ id: 1, next_action: null })],
    })
    vi.mocked(api.updateDeal).mockResolvedValue(deal({ id: 1, next_action: 'Call owner' }))
    const store = usePipelineStore()
    await store.load()
    await store.updateDeal('001', { next_action: 'Call owner' })
    expect(store.dealFor('001')?.next_action).toBe('Call owner')
  })
})
