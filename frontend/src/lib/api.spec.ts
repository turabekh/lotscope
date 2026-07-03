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

    const result = await api.search('main st', 'philadelphia')

    expect(result.query).toBe('main')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/search?q=main%20st&market=philadelphia&limit=10'),
      expect.anything(),
    )
  })

  it('ask posts the question', async () => {
    const fetchMock = mockFetch(200, {
      answer: 'Yes',
      citations: [{ source: 'Title 14', section: '14-701' }],
      confidence: 'high',
      is_informational: true,
    })
    vi.stubGlobal('fetch', fetchMock)

    const answer = await api.ask('001', 'Can I build?')

    expect(answer.citations[0]?.section).toBe('14-701')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/parcels/001/ask'),
      expect.objectContaining({ method: 'POST' }),
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

  it('redeemAppealPacket posts to the packet endpoint', async () => {
    const fetchMock = mockFetch(200, {
      parcel_number: '001',
      entitled: true,
      source: 'grant',
      packet_credits: 0,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.redeemAppealPacket('001')

    expect(result.entitled).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/parcels/001/appeal-packet'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('getParcelSummary reads the summary endpoint', async () => {
    const fetchMock = mockFetch(200, {
      parcel_number: '001',
      summary: 'A vacant lot.',
      confidence: 'medium',
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
