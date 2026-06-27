export interface ParcelDetail {
  parcel_number: string
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
  assessment_year: number | null
  lot_area_sqft: number | null
  frontage_ft: number | null
  depth_ft: number | null
  is_vacant: boolean | null
  vacancy_confidence: number | null
  is_city_owned: boolean | null
  source: string | null
  last_synced_at: string | null
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
  risk_score: number | null
  risk_flags: RiskFlag[]
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
  results: ParcelSearchResult[]
}

export interface CompResult {
  parcel_number: string
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

export interface LayerInfo {
  name: string
  source_layer: string
  tile_url: string
  fields: string[]
}

export interface LayersResponse {
  layers: LayerInfo[]
}
