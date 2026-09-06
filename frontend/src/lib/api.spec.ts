import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/lib/api'

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status',
    json: () => Promise.resolve(body),
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('search calls the search endpoint and returns the body', async () => {
    const fetchMock = mockFetch(200, { query: 'main', results: [] })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.search('main st')

    expect(result.query).toBe('main')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/search?q=main%20st&limit=10'),
      expect.anything(),
    )
  })

  it('getSheriffSales builds the query and returns the calendar', async () => {
    const fetchMock = mockFetch(200, { total: 1, returned: 1, items: [] })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.getSheriffSales({ zip: '19146', limit: 50 })

    expect(result.total).toBe(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/sheriff-sales?zip=19146&limit=50'),
      expect.anything(),
    )
  })

  it('getTopPlays builds the query and returns the feed', async () => {
    const fetchMock = mockFetch(200, { total: 1, returned: 1, plays: [] })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.getTopPlays({ zoning: 'RM', limit: 50 })

    expect(result.total).toBe(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/assemblage/top?zoning=RM&limit=50'),
      expect.anything(),
    )
  })

  it('getParcelSummary reads the summary endpoint', async () => {
    const fetchMock = mockFetch(200, {
      parcel_number: '001',
      summary: 'A vacant lot.',
      data_coverage: 'medium',
      is_informational: true,
      sources: [],
      computed_at: '2026-07-04T00:00:00Z',
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.getParcelSummary('001')

    expect(result.summary).toBe('A vacant lot.')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/parcels/001/summary'),
      expect.anything(),
    )
  })

  it('throws ApiError with the detail on a failure response', async () => {
    vi.stubGlobal('fetch', mockFetch(404, { detail: 'Parcel not found.' }))

    await expect(api.getParcel('missing')).rejects.toMatchObject({
      status: 404,
      message: 'Parcel not found.',
    })
    await expect(api.getParcel('missing')).rejects.toBeInstanceOf(ApiError)
  })
})
