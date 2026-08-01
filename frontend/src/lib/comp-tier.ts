import type { VerdictResult } from '@/lib/types'

const WIDE_AREA_TIER = 'wide_area'

interface DimensionEntry {
  dimension?: unknown
  sources?: unknown
}

interface ValuationSource {
  comp_tier?: unknown
  radius_ft?: unknown
  years?: unknown
}

function valuationSources(verdict: VerdictResult): ValuationSource[] {
  const dimensions = Array.isArray(verdict.sources) ? (verdict.sources as DimensionEntry[]) : []
  const valuation = dimensions.find(
    (entry) => entry !== null && typeof entry === 'object' && entry.dimension === 'valuation',
  )
  return Array.isArray(valuation?.sources) ? (valuation.sources as ValuationSource[]) : []
}

export function isWideAreaValuation(verdict: VerdictResult): boolean {
  return valuationSources(verdict).some((source) => source?.comp_tier === WIDE_AREA_TIER)
}

export function wideAreaSearchNote(verdict: VerdictResult): string | null {
  const source = valuationSources(verdict).find((entry) => entry?.comp_tier === WIDE_AREA_TIER)
  if (source === undefined) return null
  const radius = typeof source.radius_ft === 'number' ? Math.round(source.radius_ft) : null
  const years = typeof source.years === 'number' ? source.years : null
  if (radius === null || years === null) {
    return 'No land sales were found close by, so this uses a wider search.'
  }
  return (
    `No land sales were found close by, so this uses sales up to ` +
    `${radius.toLocaleString()} ft away and up to ${years} years old — a rough guide, ` +
    `not a market read for this block.`
  )
}
