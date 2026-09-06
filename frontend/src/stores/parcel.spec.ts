import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/lib/api'
import { useParcelStore } from '@/stores/parcel'
import type { AssemblageResult, EnvelopeResult, ParcelDetail, VerdictResult } from '@/lib/types'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ApiError: actual.ApiError,
    api: {
      getParcel: vi.fn(),
      getVerdict: vi.fn(),
      getEnvelope: vi.fn(),
      getAssemblage: vi.fn(),
      getDistress: vi.fn(),
      getNextSheriffSale: vi.fn(),
    },
  }
})

const parcel = { parcel_number: '001', owner: 'Jane' } as unknown as ParcelDetail
const verdict = { parcel_number: '001', summary: 'RSA-5' } as unknown as VerdictResult
const envelope = { parcel_number: '001', available: true } as unknown as EnvelopeResult
const assemblage = { parcel_number: '001', potential: 'high' } as unknown as AssemblageResult

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('parcel store', () => {
  it('select loads detail and verdict', async () => {
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockResolvedValue(verdict)

    const store = useParcelStore()
    await store.select('001')

    expect(store.detail?.owner).toBe('Jane')
    expect(store.verdict?.summary).toBe('RSA-5')
    expect(store.error).toBeNull()
  })

  it('leaves the verdict empty when the parcel itself is missing', async () => {
    // The verdict is computed on read, so a 404 is the parcel, not an uncomputed verdict.
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockRejectedValue(new ApiError(404, 'no parcel'))

    const store = useParcelStore()
    await store.select('001')

    expect(store.verdict).toBeNull()
    expect(store.error).toBeNull()
  })

  it('records an error when the parcel fails to load', async () => {
    vi.mocked(api.getParcel).mockRejectedValue(new ApiError(500, 'boom'))

    const store = useParcelStore()
    await store.select('001')

    expect(store.detail).toBeNull()
    expect(store.error).toBe('boom')
  })

  it('loads the envelope once and caches it per parcel', async () => {
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockResolvedValue(verdict)
    vi.mocked(api.getEnvelope).mockResolvedValue(envelope)

    const store = useParcelStore()
    await store.select('001')
    await store.loadEnvelope()
    await store.loadEnvelope()

    expect(api.getEnvelope).toHaveBeenCalledTimes(1)
    expect(store.envelope?.available).toBe(true)
  })

  it('loads assemblage for the selected parcel', async () => {
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockResolvedValue(verdict)
    vi.mocked(api.getAssemblage).mockResolvedValue(assemblage)

    const store = useParcelStore()
    await store.select('001')
    await store.loadAssemblage('001')

    expect(api.getAssemblage).toHaveBeenCalledWith('001')
    expect(store.assemblage?.potential).toBe('high')
  })

  it('loads the next sheriff sale for the selected parcel', async () => {
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockResolvedValue(verdict)
    const sale = { parcel_number: '001', case_number: 'BW-1', days_until: 12 }
    vi.mocked(api.getNextSheriffSale).mockResolvedValue(
      sale as unknown as Awaited<ReturnType<typeof api.getNextSheriffSale>>,
    )

    const store = useParcelStore()
    await store.select('001')

    expect(api.getNextSheriffSale).toHaveBeenCalledWith('001')
    expect(store.nextSheriffSale?.case_number).toBe('BW-1')
  })

  it('clears the envelope when a new parcel is selected', async () => {
    vi.mocked(api.getParcel).mockResolvedValue(parcel)
    vi.mocked(api.getVerdict).mockResolvedValue(verdict)
    vi.mocked(api.getEnvelope).mockResolvedValue(envelope)

    const store = useParcelStore()
    await store.select('001')
    await store.loadEnvelope()
    expect(store.envelope).not.toBeNull()

    await store.select('002')
    expect(store.envelope).toBeNull()
  })
})
