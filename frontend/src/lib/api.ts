import type {
  AdminOverview,
  AdminUserUpdate,
  AdminUsersResponse,
  AppealPacketStatus,
  AreaSearchRequest,
  AreaSearchResponse,
  AssemblageResult,
  AssemblageTopResponse,
  AssessmentResult,
  BasemapSession,
  BillingCadence,
  BuyerProfileDetail,
  BuyerRoster,
  BuyersNearby,
  CheckoutResponse,
  CheckoutTier,
  CorrectionCreate,
  CreditBalance,
  CreditPackKey,
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
  FetchSource,
  HistoricResult,
  JobCatalogEntry,
  JobRunSummary,
  LayersResponse,
  LeadsResponse,
  MarketContext,
  MarketInfo,
  NeighborhoodListResponse,
  NeighborhoodMarketResponse,
  NextSheriffSale,
  OfferRequest,
  OpsFleetOverview,
  OpsMarketHealthDetail,
  OpsSheriffCoverage,
  OwnerPortfolio,
  ParcelAnswer,
  ParcelChecklist,
  ParcelCompareResponse,
  ParcelDetail,
  ParcelReportResult,
  ParcelSearchResponse,
  ParcelSummaryResult,
  PipelineResponse,
  PlansResponse,
  PortalResponse,
  RegisterPayload,
  RepositoryList,
  RepositoryStatus,
  SavedSearchDetail,
  SavedSearchListResponse,
  ScenariosResult,
  SearchCriteria,
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
  getMarkets(): Promise<MarketInfo[]> {
    return request('/markets')
  },
  search(query: string, market: string, limit = 10): Promise<ParcelSearchResponse> {
    return request(
      `/search?q=${encodeURIComponent(query)}&market=${encodeURIComponent(market)}&limit=${limit}`,
    )
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
  getRepositoryStatus(parcelNumber: string): Promise<RepositoryStatus> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/repository`)
  },
  getRepositoryList(market: string): Promise<RepositoryList> {
    return request(`/sheriff-sales/repository?market=${encodeURIComponent(market)}`)
  },
  getVarianceOutlook(parcelNumber: string): Promise<VarianceOutlook> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/variance-outlook`)
  },
  getNeighborhoodMarket(market: string): Promise<NeighborhoodMarketResponse> {
    return request(`/neighborhoods/market?market=${encodeURIComponent(market)}`)
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
  getDeal(
    parcelNumber: string,
    params: { acquisitionPrice?: number | null; targetMargin?: number | null } = {},
  ): Promise<DealResult> {
    const query = new URLSearchParams()
    if (params.acquisitionPrice != null)
      query.set('acquisition_price', String(params.acquisitionPrice))
    if (params.targetMargin != null) query.set('target_margin', String(params.targetMargin))
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
  exportSavedSearch(id: number): Promise<void> {
    return downloadFile(`/saved-searches/${id}/export`, `lotscope-search-${id}.csv`)
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
  generateSavedSearchLetters(
    searchId: number,
    params: { fromName: string; fromContact: string; message?: string; onePerOwner?: boolean },
  ): Promise<void> {
    return downloadFile(
      `/outreach/letters/saved-search/${searchId}`,
      'lotscope-outreach-letters.pdf',
      {
        from_name: params.fromName,
        from_contact: params.fromContact,
        message: params.message || undefined,
        one_per_owner: params.onePerOwner,
      },
    )
  },
  getLeads(params: {
    market?: string
    minScore?: number
    vacantOnly?: boolean
    zipCode?: string
  }): Promise<LeadsResponse> {
    const query = new URLSearchParams()
    if (params.market) query.set('market', params.market)
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
  getNeighborhoods(market: string): Promise<NeighborhoodListResponse> {
    return request(`/neighborhoods?market=${encodeURIComponent(market)}`)
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
  reportCorrection(parcelNumber: string, payload: CorrectionCreate): Promise<unknown> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/corrections`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getUnderwriting(parcelNumber: string): Promise<UnderwritingAnalysis> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/underwriting`)
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
  getFetchSources(): Promise<FetchSource[]> {
    return request('/admin/fetch/sources')
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
  getBuyers(market: string, minPurchases = 3): Promise<BuyerRoster> {
    const query = new URLSearchParams({ market, min_purchases: String(minPurchases) })
    return request(`/buyers?${query.toString()}`)
  },
  getBuyer(market: string, buyerKey: string): Promise<BuyerProfileDetail> {
    const query = new URLSearchParams({ market })
    return request(`/buyers/${encodeURIComponent(buyerKey)}?${query.toString()}`)
  },
  downloadBuyersCsv(market: string): Promise<void> {
    const query = new URLSearchParams({ market })
    return downloadFile(`/buyers/export?${query.toString()}`, `lotscope-buyers-${market}.csv`)
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
  getSavedSearches(): Promise<SavedSearchListResponse> {
    return request('/saved-searches')
  },
  createSavedSearch(payload: {
    name: string
    criteria: SearchCriteria
    alerts_enabled?: boolean
  }): Promise<SavedSearchDetail> {
    return request('/saved-searches', { method: 'POST', body: JSON.stringify(payload) })
  },
  getSavedSearch(id: number): Promise<SavedSearchDetail> {
    return request(`/saved-searches/${id}`)
  },
  updateSavedSearch(
    id: number,
    payload: { name?: string; criteria?: SearchCriteria; alerts_enabled?: boolean },
  ): Promise<SavedSearchDetail> {
    return request(`/saved-searches/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
  },
  runSavedSearch(id: number): Promise<SavedSearchDetail> {
    return request(`/saved-searches/${id}/run`, { method: 'POST' })
  },
  deleteSavedSearch(id: number): Promise<void> {
    return request(`/saved-searches/${id}`, { method: 'DELETE' })
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
  refreshToken(): Promise<TokenResponse> {
    return request('/auth/refresh', { method: 'POST' })
  },
  register(payload: RegisterPayload): Promise<User> {
    return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) })
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
  getPlans(): Promise<PlansResponse> {
    return request('/billing/plans')
  },
  createCheckout(tier: CheckoutTier, cadence: BillingCadence): Promise<CheckoutResponse> {
    return request('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier, cadence }),
    })
  },
  createFoundingCheckout(): Promise<CheckoutResponse> {
    return request('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier: 'pro', cadence: 'monthly', founding: true }),
    })
  },
  createPortal(): Promise<PortalResponse> {
    return request('/billing/portal', { method: 'POST' })
  },
  getCredits(): Promise<CreditBalance> {
    return request('/credits')
  },
  skipTrace(parcelNumber: string): Promise<SkipTraceResult> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/skip-trace`, { method: 'POST' })
  },
  buyCredits(pack: CreditPackKey): Promise<CheckoutResponse> {
    return request('/billing/credits/checkout', {
      method: 'POST',
      body: JSON.stringify({ pack }),
    })
  },
  getAppealPacketStatus(parcelNumber: string): Promise<AppealPacketStatus> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/appeal-packet`)
  },
  redeemAppealPacket(parcelNumber: string): Promise<AppealPacketStatus> {
    return request(`/parcels/${encodeURIComponent(parcelNumber)}/appeal-packet`, { method: 'POST' })
  },
  appealPacketCheckout(parcelNumber: string): Promise<CheckoutResponse> {
    return request('/billing/appeal-packet/checkout', {
      method: 'POST',
      body: JSON.stringify({ parcel_number: parcelNumber }),
    })
  },
  downloadAppealPacket(parcelNumber: string): Promise<void> {
    return downloadFile(
      `/parcels/${encodeURIComponent(parcelNumber)}/appeal-packet.pdf`,
      `lotscope-assessment-review-${parcelNumber}.pdf`,
    )
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
    params: { market?: string; from?: string; to?: string; zip?: string; limit?: number } = {},
  ): Promise<SheriffSalesResponse> {
    const query = new URLSearchParams()
    if (params.market != null) query.set('market', params.market)
    if (params.from != null) query.set('from', params.from)
    if (params.to != null) query.set('to', params.to)
    if (params.zip != null) query.set('zip', params.zip)
    if (params.limit != null) query.set('limit', String(params.limit))
    const suffix = query.toString()
    return request(`/sheriff-sales${suffix ? `?${suffix}` : ''}`)
  },
  downloadSheriffIcs(market: string): Promise<void> {
    return downloadFile(
      `/sheriff-sales/calendar.ics?market=${encodeURIComponent(market)}`,
      `${market}-sales.ics`,
    )
  },
  getSheriffSubscribeUrl(market: string): Promise<{ url: string }> {
    return request(`/sheriff-sales/calendar/subscribe?market=${encodeURIComponent(market)}`)
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
