import type {
  LayersResponse,
  ParcelAnswer,
  ParcelDetail,
  ParcelSearchResponse,
  RegisterPayload,
  TokenResponse,
  Usage,
  User,
  ValuationResult,
  VerdictResult,
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
}
