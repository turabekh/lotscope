export interface ParcelDetail {
  parcel_number: string
  market_code: string
  local_key: string
  address: string | null
  zip_code: string | null
  owner: string | null
  mailing_address: string | null
  land_use: string | null
  category: string | null
  base_zoning_code: string | null
  market_value: number | null
  land_value: number | null
  improvement_value: number | null
  exempt_land: number | null
  exempt_building: number | null
  assessment_year: number | null
  lot_area_sqft: number | null
  frontage_ft: number | null
  depth_ft: number | null
  is_vacant: boolean | null
  vacancy_confidence: number | null
  is_city_owned: boolean | null
  source: string | null
  last_synced_at: string | null
  longitude: number | null
  latitude: number | null
}

export type ChecklistStatus = 'pass' | 'warn' | 'fail' | 'info'

export interface ChecklistItem {
  code: string
  category: string
  status: ChecklistStatus
  detail: string
  source: string | null
}

export interface ChecklistSummary {
  passed: number
  warnings: number
  failures: number
  info: number
  ready: boolean
}

export interface ParcelChecklist {
  parcel_number: string
  items: ChecklistItem[]
  summary: ChecklistSummary
  computed_at: string
}

export interface ParcelCompareItem {
  detail: ParcelDetail
  verdict: VerdictResult | null
}

export interface ParcelCompareResponse {
  items: ParcelCompareItem[]
}

export interface RiskFlag {
  code: string
  severity: 'high' | 'medium' | 'low' | 'info'
  label: string
  detail: string
  source: string
}

export interface VerdictResult {
  parcel_number: string
  verdict_version: string
  buildability_score: number | null
  opportunity_score: number
  summary: string
  can_build_by_right: boolean | null
  by_right_units: number | null
  max_height_ft: number | null
  needs_variance: boolean | null
  buildable_area_sqft: number | null
  value_estimate_low: number | null
  value_estimate_high: number | null
  value_confidence: number | null
  assessment_market_gap: number | null
  arv: number | null
  est_profit: number | null
  est_margin: number | null
  max_allowable_offer: number | null
  deal_score: number | null
  is_underpriced: boolean | null
  risk_score: number | null
  risk_flags: RiskFlag[]
  sources: unknown[]
  computed_at: string
}

export interface EnvelopeResult {
  parcel_number: string
  available: boolean
  district_code: string | null
  cited_section: string | null
  max_height_ft: number | null
  estimated_floors: number | null
  applied_setback_ft: number | null
  buildable_area_sqft: number | null
  lot_footprint: GeoJSON.Polygon | null
  buildable_footprint: GeoJSON.Polygon | null
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export type DealStage = 'lead' | 'diligence' | 'offer' | 'under_contract' | 'closed' | 'lost'

export interface DealItem {
  id: number
  parcel_number: string
  stage: DealStage
  note: string | null
  target_price: number | null
  address: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  opportunity_score: number | null
  updated_at: string
}

export interface PipelineResponse {
  limit: number | null
  used: number
  deals: DealItem[]
}

export interface WatchlistChange {
  code: string
  label: string
  severity: 'high' | 'medium' | 'info'
}

export interface WatchlistItem {
  parcel_number: string
  address: string | null
  owner: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  opportunity_score: number | null
  tags: string[]
  note: string | null
  created_at: string
  changes: WatchlistChange[]
  has_alerts: boolean
}

export interface WatchlistResponse {
  limit: number | null
  used: number
  alerts: number
  items: WatchlistItem[]
}

export interface SearchCriteria {
  vacant_only: boolean
  exclude_city_owned: boolean
  zoning_codes: string[]
  zip_code: string | null
  min_market_value: number | null
  max_market_value: number | null
  min_lot_area_sqft: number | null
  max_lot_area_sqft: number | null
  min_opportunity_score: number | null
  min_distress_score: number | null
  is_delinquent: boolean | null
  in_sheriff_sale: boolean | null
}

export interface SavedSearchMatchItem {
  parcel_number: string
  address: string | null
  owner: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  opportunity_score: number | null
  first_seen_at: string
  is_new: boolean
}

export interface SavedSearchItem {
  id: number
  name: string
  criteria: SearchCriteria
  alerts_enabled: boolean
  created_at: string
  last_run_at: string | null
  match_count: number
  new_count: number
}

export interface SavedSearchDetail extends SavedSearchItem {
  matches: SavedSearchMatchItem[]
}

export interface SavedSearchListResponse {
  limit: number | null
  used: number
  searches: SavedSearchItem[]
}

export interface GeoPoint {
  lat: number
  lng: number
}

export interface AreaSearchRequest {
  center?: GeoPoint
  radius_m?: number
  polygon?: GeoJSON.Polygon
  neighborhood?: string
  vacant_only?: boolean
  zoning_codes?: string[]
  min_lot_area_sqft?: number
  max_lot_area_sqft?: number
  min_market_value?: number
  max_market_value?: number
  min_opportunity_score?: number
  min_distress_score?: number
  delinquent_only?: boolean
  sheriff_sale_only?: boolean
  underpriced_only?: boolean
  by_right_only?: boolean
  limit?: number
}

export interface OwnerParcel {
  parcel_number: string
  address: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  opportunity_score: number | null
}

export interface OwnerPortfolio {
  owner: string | null
  mailing_address: string | null
  total_count: number
  vacant_count: number
  total_market_value: number | null
  shown: number
  parcels: OwnerParcel[]
}

export interface DeedRestrictionItem {
  kind: string
  text: string
  citation: string | null
  confidence: string
  document_type: string | null
  recording_date: string | null
}

export interface RecordedDeedItem {
  document_id: string
  document_type: string | null
  recording_date: string | null
  grantor: string | null
  grantee: string | null
  sale_price: number | null
  analyzed: boolean
  record_url: string | null
}

export interface DeedRestrictionsResponse {
  parcel_number: string
  count: number
  restrictions: DeedRestrictionItem[]
  deeds: RecordedDeedItem[]
}

export interface NeighborhoodSummary {
  name: string
}

export interface NeighborhoodListResponse {
  neighborhoods: NeighborhoodSummary[]
}

export interface SpatialParcelResult {
  parcel_number: string
  address: string | null
  owner: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  opportunity_score: number | null
  lng: number | null
  lat: number | null
  distance_m: number | null
}

export interface AreaSearchResponse {
  count: number
  total: number
  truncated: boolean
  results: SpatialParcelResult[]
}

export type DistressTier = 'high' | 'medium' | 'low' | 'none'

export interface DistressFactor {
  code: string
  label: string
  weight: number
}

export interface DistressResult {
  parcel_number: string
  score: number
  tier: DistressTier
  factors: DistressFactor[]
  sources: unknown[]
  computed_at: string
}

export interface NeighborhoodMarketStats {
  name: string
  vacant_lots: number
  avg_distress: number | null
  avg_opportunity: number | null
  median_market_value: number | null
  tax_delinquent: number
  sheriff_sale: number
}

export interface MarketTotals {
  neighborhoods: number
  vacant_lots: number
  tax_delinquent: number
  sheriff_sale: number
}

export interface NeighborhoodMarketResponse {
  totals: MarketTotals
  neighborhoods: NeighborhoodMarketStats[]
  computed_at: string
}

export interface NextSheriffSale {
  parcel_number: string
  case_number: string
  sale_type: string | null
  sale_date: string
  status: string | null
  opening_bid: number | null
  days_until: number
}

export type AssessmentStatus = 'over_assessed' | 'fairly_assessed' | 'under_assessed' | 'unknown'

export interface AppealPacketStatus {
  parcel_number: string
  entitled: boolean
  source: string | null
  packet_credits: number
}

export interface ParcelSummaryResult {
  parcel_number: string
  verdict_version: string
  summary: string
  data_coverage: 'high' | 'medium' | 'low'
  is_informational: boolean
  sources: Array<Record<string, unknown>>
  computed_at: string
}

export interface VarianceOutlook {
  parcel_number: string
  district: string | null
  population_label: string
  window_months: number
  decided: number
  granted: number
  grant_rate: number | null
  local_scope: string | null
  local_decided: number | null
  local_grant_rate: number | null
  reason: string | null
  sources: Array<Record<string, unknown>>
  computed_at: string
}

export interface ReportSection {
  heading: string
  body: string
}

export interface ParcelReportResult {
  parcel_number: string
  headline: string
  sections: ReportSection[]
  recommendation: string
  confidence: 'high' | 'medium' | 'low'
  is_informational: boolean
  sources: Array<Record<string, unknown>>
  computed_at: string
}

export interface AssessmentResult {
  parcel_number: string
  status: AssessmentStatus
  assessed_market_value: number | null
  market_estimate: number | null
  market_low: number | null
  market_high: number | null
  gap: number | null
  gap_pct: number | null
  over_assessed_amount: number | null
  estimated_annual_tax_savings: number | null
  tax_rate: number
  confidence: 'high' | 'medium' | 'low'
  reasons: string[]
  disclaimer: string
  sources: unknown[]
  computed_at: string
}

export interface ScenarioItem {
  units: number
  by_right: boolean
  arv: number | null
  total_cost: number | null
  profit: number | null
  margin: number | null
  roi: number | null
  max_allowable_offer: number | null
  deal_score: number | null
}

export interface ScenariosResult {
  parcel_number: string
  by_right_units: number | null
  recommended_units: number | null
  scenarios: ScenarioItem[]
  confidence: 'high' | 'medium' | 'low'
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export interface MarketContext {
  parcel_number: string
  neighborhood: string | null
  radius_ft: number
  years: number
  parcels_nearby: number
  vacant_nearby: number
  vacancy_rate: number | null
  median_assessed_value: number | null
  recent_sales: number
  sales_per_year: number | null
  median_sale_price: number | null
  permits: number
  demolitions: number
  sources: unknown[]
  computed_at: string
}

export interface HistoricResult {
  parcel_number: string
  in_historic_district: boolean
  district_name: string | null
  designated_date: string | null
  note: string | null
  sources: unknown[]
  computed_at: string
}

export type SubdivisionLimitingFactor = 'area' | 'width' | 'both' | 'none'

export interface SubdivisionResult {
  parcel_number: string
  district_code: string | null
  can_subdivide: boolean
  max_lots: number | null
  limiting_factor: SubdivisionLimitingFactor | null
  is_conforming: boolean | null
  needs_consolidation: boolean
  lot_area_sqft: number | null
  lot_width_ft: number | null
  min_lot_area_sqft: number | null
  min_lot_width_ft: number | null
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export interface DealAssumptions {
  construction_cost_per_sqft: number
  soft_cost_pct: number
  selling_cost_pct: number
  target_margin: number
  default_unit_sqft: number
  max_unit_sqft: number
}

export interface DealResult {
  parcel_number: string
  units: number | null
  arv: number | null
  per_unit_value: number | null
  gross_floor_area_sqft: number | null
  acquisition_cost: number | null
  construction_cost: number | null
  soft_cost: number | null
  selling_cost: number | null
  total_cost: number | null
  profit: number | null
  margin: number | null
  roi: number | null
  max_allowable_offer: number | null
  is_underpriced: boolean | null
  deal_score: number | null
  comp_count: number
  confidence: 'high' | 'medium' | 'low'
  assumptions: DealAssumptions
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export interface LeadItem {
  parcel_number: string
  address: string | null
  owner: string | null
  base_zoning_code: string | null
  is_vacant: boolean | null
  market_value: number | null
  total_due: number | null
  in_sheriff_sale: boolean | null
  score: number
  top_factors: string[]
  deal_score: number | null
  max_allowable_offer: number | null
  is_underpriced: boolean | null
}

export interface LeadsResponse {
  tier: string
  limit: number
  returned: number
  leads: LeadItem[]
}

export type Acquirability = 'same_owner' | 'city_owned' | 'vacant' | 'built'
export type AssemblagePotential = 'high' | 'medium' | 'low' | 'none'

export interface AdjacentLot {
  parcel_number: string
  address: string | null
  owner: string | null
  base_zoning_code: string | null
  lot_area_sqft: number | null
  frontage_ft: number | null
  market_value: number | null
  is_vacant: boolean | null
  is_city_owned: boolean | null
  same_owner: boolean
  same_zoning: boolean
  shared_boundary_ft: number | null
  acquirability: Acquirability
  is_candidate: boolean
}

export interface AssemblageSummary {
  adjacent_count: number
  candidate_count: number
  combined_lot_area_sqft: number | null
  combined_frontage_ft: number | null
  by_right_units_current: number | null
  by_right_units_combined: number | null
  units_basis: 'per_unit' | 'far_estimate' | 'flat_cap' | null
  has_same_owner_neighbor: boolean
  has_city_owned_neighbor: boolean
  has_vacant_neighbor: boolean
}

export interface AssemblageResult {
  parcel_number: string
  potential: AssemblagePotential
  summary: AssemblageSummary
  neighbors: AdjacentLot[]
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export interface ParcelSearchResult {
  parcel_number: string
  address: string | null
  owner: string | null
  score: number
}

export interface ParcelSearchResponse {
  query: string
  market: string
  results: ParcelSearchResult[]
}

export interface CompResult {
  parcel_number: string
  address: string | null
  distance_ft: number
  sale_price: number
  sale_date: string | null
  lot_area_sqft: number | null
  price_per_sqft: number | null
}

export interface ValuationResult {
  parcel_number: string
  estimate: number | null
  low: number | null
  high: number | null
  price_per_sqft: number | null
  confidence: 'high' | 'medium' | 'low'
  comp_count: number
  coefficient_of_variation: number | null
  comps: CompResult[]
  reasons: string[]
  sources: unknown[]
  computed_at: string
}

export interface Citation {
  source: string
  section: string
}

export interface ParcelAnswer {
  answer: string
  citations: Citation[]
  confidence: 'high' | 'medium' | 'low'
  is_informational: boolean
}

export interface BasemapSession {
  map_type: string
  tile_url: string
  attribution: string
  tile_size: number
}

export interface LayerInfo {
  name: string
  source_layer: string
  tile_url: string
  fields: string[]
}

export interface LayersResponse {
  layers: LayerInfo[]
}

export interface User {
  id: number
  email: string
  full_name: string | null
  role: string
  tier: string
  is_active: boolean
  subscription_status: string | null
  digest_frequency: 'off' | 'weekly' | 'daily'
  created_at: string
}

export interface DatasetStatus {
  dataset: string
  status: string
  last_attempt_at: string | null
  last_success_at: string | null
  row_count: number | null
  detail: string | null
}

export interface AdminOverview {
  users_total: number
  users_by_tier: Record<string, number>
  parcels_total: number
  parcels_vacant: number
  verdicts_total: number
  deeds_total: number
  saved_searches_total: number
  neighborhoods_total: number
}

export interface AdminUsersResponse {
  total: number
  users: User[]
}

export interface AdminUserUpdate {
  role?: string
  tier?: string
  is_active?: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export type BillingCadence = 'monthly' | 'annual'
export type CheckoutTier = 'pro' | 'investor'
export type CreditPackKey = 'small' | 'medium' | 'large'

export interface SkipTraceContacts {
  phones: string[]
  emails: string[]
}

export interface SkipTraceResult {
  parcel_number: string
  owner: string | null
  contacts: SkipTraceContacts
  credits_spent: number
  credits_remaining: number
  cached: boolean
}

export interface CreditLedgerItem {
  delta: number
  reason: string
  ref: string | null
  created_at: string
}

export interface CreditBalance {
  balance: number
  entries: CreditLedgerItem[]
}

export interface FeedSummaryItem {
  code: string
  label: string
  count: number
}

export interface FeedEvent {
  parcel_number: string
  address: string | null
  code: string
  label: string
  severity: 'high' | 'medium' | 'low'
  detected_at: string
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
  opportunity_score: number | null
}

export interface FeedResponse {
  since: string
  total: number
  returned: number
  summary: FeedSummaryItem[]
  events: FeedEvent[]
}

export interface SheriffSaleItem {
  parcel_number: string
  address: string | null
  case_number: string
  sale_type: string | null
  sale_date: string | null
  status: string | null
  opening_bid: number | null
  plaintiff: string | null
  max_allowable_offer: number | null
  bid_gap: number | null
  opportunity_score: number | null
}

export interface SheriffSalesResponse {
  total: number
  returned: number
  items: SheriffSaleItem[]
}

export interface AssemblageTopPlay {
  parcel_number: string
  address: string | null
  potential: 'high' | 'medium' | 'low' | 'none'
  candidate_count: number
  combined_lot_area_sqft: number | null
  by_right_units_current: number | null
  by_right_units_combined: number | null
  unit_unlock: number | null
  base_zoning_code: string | null
  neighborhood: string | null
}

export interface AssemblageTopResponse {
  total: number
  returned: number
  plays: AssemblageTopPlay[]
}

export interface PlanInfo {
  tier: string
  name: string
  tagline: string
  price_monthly_cents: number | null
  price_annual_cents: number | null
  action: 'current' | 'checkout' | 'contact'
  highlights: string[]
  is_current: boolean
}

export interface PlansResponse {
  plans: PlanInfo[]
  contact_url: string
}

export interface CheckoutResponse {
  url: string
}

export interface PortalResponse {
  url: string
}

export interface RegisterPayload {
  email: string
  password: string
  full_name?: string | null
}

export interface UsageMetric {
  limit: number | null
  used: number
  remaining: number | null
}

export interface Usage {
  tier: string
  ask: UsageMetric
  parcel_views: UsageMetric
}
