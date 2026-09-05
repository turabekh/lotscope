import type {
  DealOverrides,
  PolicyDocument,
  PolicySummary,
  CorrectionRecord,
  BuyBoxPayload,
  CheckoutPrices,
  CheckoutSession,
  PacketRecord,
  BriefRecord,
  BuyBoxRecord,
  BuyBoxMatches,
  OwnedParcelSeedResult,
  AdminOverview,
  AdminUserUpdate,
  AdminUsersResponse,
  AreaSearchRequest,
  AreaSearchResponse,
  AssemblageResult,
  AssemblageTopResponse,
  AssessmentResult,
  BasemapSession,
  BuyerProfileDetail,
  BuyerRoster,
  BuyersNearby,
  CorrectionCreate,
  CorrectionResolve,
  CorrectionStatus,
  DatasetStatus,
  DealActivityItem,
  DealItem,
  DealResult,
  DealStage,
  DealUpdatePayload,
  DeedRestrictionsResponse,
  DistressResult,
  EnvelopeResult,
  FeedResponse,
  HistoricResult,
  JobCatalogEntry,
  JobRunSummary,
  LayersResponse,
  LeadsResponse,
  MarketContext,
  NeighborhoodListResponse,
  NeighborhoodMarketResponse,
  NextSheriffSale,
  OfferRequest,
  OpsFleetOverview,
  OpsMarketHealthDetail,
  OpsSheriffCoverage,
  OwnerPortfolio,
  ParcelChecklist,
  ParcelCompareResponse,
  ParcelDetail,
  ParcelReportResult,
  ParcelSearchResponse,
  ParcelSummaryResult,
  PipelineResponse,
  RegisterPayload,
  VerificationPending,
  ScenariosResult,
  SheriffSalesResponse,
  SignerProfile,
  SkipTraceResult,
  SourceFreshness,
  SubdivisionResult,
  TokenResponse,
  UnderwritingAnalysis,
  Usage,
  User,
  ValuationResult,
  VarianceOutlook,
  VerdictResult,
  WatchlistResponse,
} from '@/lib/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let authToken: string | null = null
let unauthorizedHandler: (() => void) | null = null
let emailUnverifiedHandler: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

export function setEmailUnverifiedHandler(handler: (() => void) | null): void {
  emailUnverifiedHandler = handler
}

const UNAUTHENTICATED_PATHS = [
  '/auth/login',
  '/auth/register',
  '/auth/verify',
  '/auth/resend-verification',
]

function reportUnauthorized(path: string): void {
  if (UNAUTHENTICATED_PATHS.some((candidate) => path.startsWith(candidate))) return
  unauthorizedHandler?.()
}

export const EMAIL_UNVERIFIED_CODE = 'email_unverified'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string | null = null,
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
    if (response.status === 401) reportUnauthorized(path)
    const body = (await response.json().catch(() => null)) as {
      detail?: string
      code?: string
    } | null
    if (body?.code === EMAIL_UNVERIFIED_CODE) emailUnverifiedHandler?.()
    throw new ApiError(response.status, body?.detail ?? response.statusText, body?.code ?? null)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function uploadRequest<T>(path: string, body: FormData): Promise<T> {
  const headers: Record<string, string> = {}
  if (authToken !== null) headers.authorization = `Bearer ${authToken}`
  const response = await fetch(`${BASE_URL}${path}`, { method: 'POST', body, headers })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, payload?.detail ?? response.statusText)
  }
  return (await response.json()) as T
}

async function downloadFile(path: string, filename: string, body?: unknown): Promise<void> {
  const headers: Record<string, string> = {}
  if (authToken !== null) headers.authorization = `Bearer ${authToken}`
  const init: RequestInit = { headers }
  if (body !== undefined) {
    init.method = 'POST'
    headers['content-type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  const response = await fetch(`${BASE_URL}${path}`, init)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
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
  getNextSheriffSale(parcelNumber: string): Promise<NextSheriffSale | null> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/next-sheriff-sale`)
  },
  getVarianceOutlook(parcelNumber: string): Promise<VarianceOutlook> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/variance-outlook`)
  },
  getNeighborhoodMarket(): Promise<NeighborhoodMarketResponse> {
    return request('/neighborhoods/market')
  },
  getParcelSummary(parcelNumber: string): Promise<ParcelSummaryResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/summary`)
  },
  getParcelReport(parcelNumber: string): Promise<ParcelReportResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/report`)
  },
  getAssessment(parcelNumber: string): Promise<AssessmentResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/assessment`)
  },
  getSubdivision(parcelNumber: string): Promise<SubdivisionResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/subdivision`)
  },
  getHistoric(parcelNumber: string): Promise<HistoricResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/historic`)
  },
  getMarketContext(parcelNumber: string): Promise<MarketContext> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/market`)
  },
  getScenarios(parcelNumber: string): Promise<ScenariosResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/scenarios`)
  },
  getChecklist(parcelNumber: string): Promise<ParcelChecklist> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/checklist`)
  },
  compareParcels(parcelNumbers: string[]): Promise<ParcelCompareResponse> {
    const query = parcelNumbers
      .map((parcelNumber) => `parcels=${encodeURIComponent(parcelNumber)}`)
      .join('&')
    return request(`/parcels/compare?${query}`)
  },
  getDeal(parcelNumber: string, params: DealOverrides = {}): Promise<DealResult> {
    const query = new URLSearchParams()
    if (params.acquisitionPrice != null)
      query.set('acquisition_price', String(params.acquisitionPrice))
    if (params.targetMargin != null) query.set('target_margin', String(params.targetMargin))
    if (params.constructionCostPerSqft != null)
      query.set('construction_cost_per_sqft', String(params.constructionCostPerSqft))
    const qs = query.toString()
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/deal${qs ? `?${qs}` : ''}`)
  },
  async downloadDossier(parcelNumber: string): Promise<void> {
    const headers: Record<string, string> = {}
    if (authToken !== null) headers.authorization = `Bearer ${authToken}`
    const response = await fetch(
      `${BASE_URL}/parcels/${encodeURIComponent(parcelNumber)}/dossier`,
      { headers },
    )
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new ApiError(response.status, body?.detail ?? response.statusText)
    }
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = `lotscope-dossier-${parcelNumber}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
  exportLeads(params: {
    minScore?: number
    vacantOnly?: boolean
    zipCode?: string
  }): Promise<void> {
    const query = new URLSearchParams()
    if (params.minScore != null) query.set('min_score', String(params.minScore))
    if (params.vacantOnly) query.set('vacant_only', 'true')
    if (params.zipCode) query.set('zip_code', params.zipCode)
    return downloadFile(`/leads/export?${query.toString()}`, 'lotscope-leads.csv')
  },
  exportPipeline(): Promise<void> {
    return downloadFile('/pipeline/export', 'lotscope-pipeline.csv')
  },
  generateOutreachLetters(params: {
    fromName: string
    fromContact: string
    message?: string
    minScore?: number
    vacantOnly?: boolean
    zipCode?: string
    onePerOwner?: boolean
  }): Promise<void> {
    return downloadFile('/outreach/letters', 'lotscope-outreach-letters.pdf', {
      from_name: params.fromName,
      from_contact: params.fromContact,
      message: params.message || undefined,
      min_score: params.minScore,
      vacant_only: params.vacantOnly,
      zip_code: params.zipCode,
      one_per_owner: params.onePerOwner,
    })
  },
  generateWatchlistLetters(params: {
    fromName: string
    fromContact: string
    message?: string
    onePerOwner?: boolean
  }): Promise<void> {
    return downloadFile('/outreach/letters/watchlist', 'lotscope-outreach-letters.pdf', {
      from_name: params.fromName,
      from_contact: params.fromContact,
      message: params.message || undefined,
      one_per_owner: params.onePerOwner,
    })
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
  addToWatchlist(
    parcelNumber: string,
    tags: string[] = [],
    note: string | null = null,
  ): Promise<void> {
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
  getPipeline(): Promise<PipelineResponse> {
    return request('/pipeline')
  },
  addToPipeline(parcelNumber: string, stage: DealStage = 'lead'): Promise<DealItem> {
    return request('/pipeline', {
      method: 'POST',
      body: JSON.stringify({ parcel_number: parcelNumber, stage }),
    })
  },
  updateDeal(parcelNumber: string, payload: DealUpdatePayload): Promise<DealItem> {
    return request(`/pipeline/${encodeURIComponent(parcelNumber)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  getPipelineToday(): Promise<{ deals: DealItem[] }> {
    return request('/pipeline/today')
  },
  getDealActivity(parcelNumber: string): Promise<DealActivityItem[]> {
    return request(`/pipeline/${encodeURIComponent(parcelNumber)}/activity`)
  },
  removeFromPipeline(parcelNumber: string): Promise<void> {
    return request(`/pipeline/${encodeURIComponent(parcelNumber)}`, { method: 'DELETE' })
  },
  searchArea(payload: AreaSearchRequest): Promise<AreaSearchResponse> {
    return request('/search/area', { method: 'POST', body: JSON.stringify(payload) })
  },
  getNeighborhoods(): Promise<NeighborhoodListResponse> {
    return request('/neighborhoods')
  },
  getAdminOverview(): Promise<AdminOverview> {
    return request('/admin/overview')
  },
  getAdminDatasets(): Promise<DatasetStatus[]> {
    return request('/admin/datasets')
  },
  getAdminUsers(limit = 50, offset = 0): Promise<AdminUsersResponse> {
    return request(`/admin/users?limit=${limit}&offset=${offset}`)
  },
  updateAdminUser(userId: number, payload: AdminUserUpdate): Promise<User> {
    return request(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) })
  },
  getCorrectionQueue(status?: CorrectionStatus, limit = 100): Promise<CorrectionRecord[]> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (status) query.set('status', status)
    return request(`/admin/corrections?${query.toString()}`)
  },
  triageCorrection(correctionId: number, payload: CorrectionResolve): Promise<CorrectionRecord> {
    return request(`/admin/corrections/${correctionId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  reportCorrection(parcelNumber: string, payload: CorrectionCreate): Promise<unknown> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/corrections`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getPolicyIndex(): Promise<PolicySummary[]> {
    return request('/policies')
  },
  getPolicy(slug: string): Promise<PolicyDocument> {
    return request(`/policies/${encodeURIComponent(slug)}`)
  },
  getOwnCorrections(): Promise<CorrectionRecord[]> {
    return request('/corrections')
  },
  getCheckoutPrices(): Promise<CheckoutPrices> {
    return request('/checkout/prices')
  },

  getPackets(): Promise<PacketRecord[]> {
    return request('/packets')
  },

  getBriefs(): Promise<BriefRecord[]> {
    return request('/briefs')
  },

  // Null is an answer: nothing changed overnight.
  todaysBrief(): Promise<BriefRecord | null> {
    return request('/briefs/today')
  },

  downloadPacket(packetId: number, saleDate: string): Promise<void> {
    return downloadFile(`/packets/${packetId}/download`, `lotscope-sale-packet-${saleDate}.pdf`)
  },

  startCheckout(sku: 'packet' | 'diligence', objectRef: string): Promise<CheckoutSession> {
    return request('/checkout', {
      method: 'POST',
      body: JSON.stringify({ sku, object_ref: objectRef }),
    })
  },

  getBuyBox(): Promise<BuyBoxRecord> {
    return request('/me/buy-box')
  },

  saveBuyBox(payload: BuyBoxPayload): Promise<BuyBoxRecord> {
    return request('/me/buy-box', { method: 'PUT', body: JSON.stringify(payload) })
  },

  seedOwnedParcels(ownerName: string): Promise<OwnedParcelSeedResult> {
    return request('/me/buy-box/owned-parcels/seed', {
      method: 'POST',
      body: JSON.stringify({ owner_name: ownerName }),
    })
  },

  getBuyBoxMatches(limit = 5): Promise<BuyBoxMatches> {
    return request(`/underwriting/matches?limit=${limit}`)
  },
  getUnderwriting(
    parcelNumber: string,
    overrides: DealOverrides = {},
  ): Promise<UnderwritingAnalysis> {
    const query = new URLSearchParams()
    if (overrides.acquisitionPrice != null) {
      query.set('acquisition_price', String(overrides.acquisitionPrice))
    }
    if (overrides.targetMargin != null) {
      query.set('target_margin', String(overrides.targetMargin))
    }
    if (overrides.constructionCostPerSqft != null) {
      query.set('construction_cost_per_sqft', String(overrides.constructionCostPerSqft))
    }
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/underwriting${suffix}`)
  },
  getParcelFreshness(parcelNumber: string): Promise<SourceFreshness[]> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/freshness`)
  },
  getJobCatalog(): Promise<JobCatalogEntry[]> {
    return request('/admin/jobs')
  },
  getJobRuns(limit = 50): Promise<JobRunSummary[]> {
    return request(`/admin/jobs/runs?limit=${limit}`)
  },
  runJob(jobId: string, params: Record<string, string> = {}): Promise<JobRunSummary> {
    return request('/admin/jobs/run', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, params }),
    })
  },
  getOpsFleet(): Promise<OpsFleetOverview> {
    return request('/admin/ops/fleet')
  },
  getOpsMarketHealth(marketCode: string): Promise<OpsMarketHealthDetail> {
    return request(`/admin/ops/markets/${encodeURIComponent(marketCode)}`)
  },
  runSheriffCoverage(): Promise<OpsSheriffCoverage> {
    return request('/admin/ops/sheriff-coverage', { method: 'POST' })
  },
  pullSource(url: string, filename: string): Promise<void> {
    return downloadFile(`/admin/fetch?url=${encodeURIComponent(url)}`, filename)
  },
  getParcelBuyers(parcelNumber: string): Promise<BuyersNearby> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/buyers`)
  },
  getBuyers(minPurchases = 3): Promise<BuyerRoster> {
    const query = new URLSearchParams({ min_purchases: String(minPurchases) })
    return request(`/buyers?${query.toString()}`)
  },
  getBuyer(buyerKey: string): Promise<BuyerProfileDetail> {
    return request(`/buyers/${encodeURIComponent(buyerKey)}`)
  },
  downloadBuyersCsv(): Promise<void> {
    return downloadFile('/buyers/export', 'lotscope-buyers.csv')
  },
  generateOffer(parcelNumber: string, payload: OfferRequest): Promise<void> {
    const slug = parcelNumber.replace(/:/g, '-')
    return downloadFile(
      `/pipeline/${encodeURIComponent(parcelNumber)}/offer`,
      `lotscope-loi-${slug}.pdf`,
      payload,
    )
  },
  updateSigner(payload: SignerProfile): Promise<User> {
    return request('/auth/signer', { method: 'PATCH', body: JSON.stringify(payload) })
  },
  getOwnerPortfolio(parcelNumber: string): Promise<OwnerPortfolio> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/owner-portfolio`)
  },
  analyzeDeed(
    parcelNumber: string,
    documentId: string,
    file: File,
  ): Promise<DeedRestrictionsResponse> {
    const form = new FormData()
    form.append('file', file)
    return uploadRequest(
      `/parcels/${encodeURIComponent(parcelNumber)}/deeds/${encodeURIComponent(documentId)}/analyze`,
      form,
    )
  },
  getDeedRestrictions(parcelNumber: string): Promise<DeedRestrictionsResponse> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/deed-restrictions`)
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
  refreshToken(): Promise<TokenResponse> {
    return request('/auth/refresh', { method: 'POST' })
  },
  register(payload: RegisterPayload): Promise<VerificationPending> {
    return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) })
  },
  verifyEmail(token: string): Promise<TokenResponse> {
    return request('/auth/verify', { method: 'POST', body: JSON.stringify({ token }) })
  },
  resendVerification(email: string): Promise<VerificationPending> {
    return request('/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },
  getMe(): Promise<User> {
    return request('/auth/me')
  },
  setDigestPreference(frequency: 'off' | 'weekly' | 'daily'): Promise<User> {
    return request('/auth/digest', { method: 'PATCH', body: JSON.stringify({ frequency }) })
  },
  markOnboarded(): Promise<User> {
    return request('/auth/onboarded', { method: 'POST' })
  },
  getVapidPublicKey(): Promise<{ public_key: string | null }> {
    return request('/push/vapid-public-key')
  },
  pushSubscribe(subscription: {
    endpoint: string
    keys: { p256dh: string; auth: string }
  }): Promise<void> {
    return request('/push/subscribe', { method: 'POST', body: JSON.stringify(subscription) })
  },
  pushUnsubscribe(endpoint: string): Promise<void> {
    return request('/push/unsubscribe', { method: 'POST', body: JSON.stringify({ endpoint }) })
  },
  getUsage(): Promise<Usage> {
    return request('/auth/usage')
  },
  skipTrace(parcelNumber: string): Promise<SkipTraceResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/skip-trace`, { method: 'POST' })
  },
  getFeed(
    params: { days?: number; savedSearchId?: number; limit?: number } = {},
  ): Promise<FeedResponse> {
    const query = new URLSearchParams()
    if (params.days != null) query.set('days', String(params.days))
    if (params.savedSearchId != null) query.set('saved_search_id', String(params.savedSearchId))
    if (params.limit != null) query.set('limit', String(params.limit))
    const suffix = query.toString()
    return request(`/feed${suffix ? `?${suffix}` : ''}`)
  },
  getSheriffSales(
    params: { from?: string; to?: string; zip?: string; limit?: number } = {},
  ): Promise<SheriffSalesResponse> {
    const query = new URLSearchParams()
    if (params.from != null) query.set('from', params.from)
    if (params.to != null) query.set('to', params.to)
    if (params.zip != null) query.set('zip', params.zip)
    if (params.limit != null) query.set('limit', String(params.limit))
    const suffix = query.toString()
    return request(`/sheriff-sales${suffix ? `?${suffix}` : ''}`)
  },
  downloadSheriffIcs(): Promise<void> {
    return downloadFile('/sheriff-sales/calendar.ics', 'phl-sales.ics')
  },
  getSheriffSubscribeUrl(): Promise<{ url: string }> {
    return request('/sheriff-sales/calendar/subscribe')
  },
  getTopPlays(
    params: { neighborhood?: string; zoning?: string; limit?: number } = {},
  ): Promise<AssemblageTopResponse> {
    const query = new URLSearchParams()
    if (params.neighborhood != null) query.set('neighborhood', params.neighborhood)
    if (params.zoning != null) query.set('zoning', params.zoning)
    if (params.limit != null) query.set('limit', String(params.limit))
    const suffix = query.toString()
    return request(`/assemblage/top${suffix ? `?${suffix}` : ''}`)
  },
}
