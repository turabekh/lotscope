import type {
  AssemblageResult,
  BasemapSession,
  BillingCadence,
  CheckoutResponse,
  DistressResult,
  EnvelopeResult,
  LayersResponse,
  LeadsResponse,
  ParcelAnswer,
  ParcelDetail,
  ParcelSearchResponse,
  PlansResponse,
  PortalResponse,
  RegisterPayload,
  TokenResponse,
  Usage,
  User,
  ValuationResult,
  VerdictResult,
  WatchlistResponse,
} from '@/lib/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let authToken: string | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

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
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    ...((init?.headers as Record<string, string>) ?? {}),
  }
  if (authToken !== null) headers.authorization = `Bearer ${authToken}`
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  if (response.status === 204) return undefined as T
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
  getEnvelope(parcelNumber: string): Promise<EnvelopeResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/envelope`)
  },
  getAssemblage(parcelNumber: string): Promise<AssemblageResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/assemblage`)
  },
  getDistress(parcelNumber: string): Promise<DistressResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/distress`)
  },
  getLeads(params: {
    minScore?: number
    vacantOnly?: boolean
    zipCode?: string
  }): Promise<LeadsResponse> {
    const query = new URLSearchParams()
    if (params.minScore != null) query.set('min_score', String(params.minScore))
    if (params.vacantOnly) query.set('vacant_only', 'true')
    if (params.zipCode) query.set('zip_code', params.zipCode)
    return request(`/leads?${query.toString()}`)
  },
  getWatchlist(): Promise<WatchlistResponse> {
    return request('/watchlist')
  },
  addToWatchlist(parcelNumber: string, tags: string[] = [], note: string | null = null): Promise<void> {
    return request('/watchlist', {
      method: 'POST',
      body: JSON.stringify({ parcel_number: parcelNumber, tags, note }),
    })
  },
  updateWatchlistItem(
    parcelNumber: string,
    payload: { tags?: string[]; note?: string | null },
  ): Promise<void> {
    return request(`/watchlist/${encodeURIComponent(parcelNumber)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  removeFromWatchlist(parcelNumber: string): Promise<void> {
    return request(`/watchlist/${encodeURIComponent(parcelNumber)}`, { method: 'DELETE' })
  },
  markWatchlistSeen(parcelNumber: string): Promise<void> {
    return request(`/watchlist/${encodeURIComponent(parcelNumber)}/seen`, { method: 'POST' })
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
  getBasemapSession(mapType: 'satellite' | 'roadmap'): Promise<BasemapSession> {
    return request(`/maps/basemap-session?map_type=${mapType}`)
  },
  getBasemapAttribution(
    mapType: 'satellite' | 'roadmap',
    bounds: { north: number; south: number; east: number; west: number },
    zoom: number,
  ): Promise<{ attribution: string }> {
    const query =
      `map_type=${mapType}&zoom=${zoom}` +
      `&north=${bounds.north}&south=${bounds.south}&east=${bounds.east}&west=${bounds.west}`
    return request(`/maps/attribution?${query}`)
  },
  login(email: string, password: string): Promise<TokenResponse> {
    return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
  },
  register(payload: RegisterPayload): Promise<User> {
    return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) })
  },
  getMe(): Promise<User> {
    return request('/auth/me')
  },
  getUsage(): Promise<Usage> {
    return request('/auth/usage')
  },
  getPlans(): Promise<PlansResponse> {
    return request('/billing/plans')
  },
  createCheckout(cadence: BillingCadence): Promise<CheckoutResponse> {
    return request('/billing/checkout', { method: 'POST', body: JSON.stringify({ cadence }) })
  },
  createPortal(): Promise<PortalResponse> {
    return request('/billing/portal', { method: 'POST' })
  },
}
