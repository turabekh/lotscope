import type {
  LayersResponse,
  ParcelAnswer,
  ParcelDetail,
  ParcelSearchResponse,
  ValuationResult,
  VerdictResult,
} from '@/lib/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  return (await response.json()) as T
}

export const api = {
  search(query: string, limit = 10): Promise<ParcelSearchResponse> {
    return request(`/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  },
  getParcel(parcelNumber: string): Promise<ParcelDetail> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}`)
  },
  getVerdict(parcelNumber: string): Promise<VerdictResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/verdict`)
  },
  refreshVerdict(parcelNumber: string): Promise<VerdictResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/verdict/refresh`, {
      method: 'POST',
    })
  },
  getComps(parcelNumber: string): Promise<ValuationResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/comps`)
  },
  ask(parcelNumber: string, question: string): Promise<ParcelAnswer> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    })
  },
  getLayers(): Promise<LayersResponse> {
    return request('/layers')
  },
}
