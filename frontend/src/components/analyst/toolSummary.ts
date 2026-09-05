import type { ToolCall } from '@/stores/analyst'

/**
 * The one line a tool call shows before anyone expands it.
 *
 * A buyer scanning a thread wants to know what was checked and what it found, not that a
 * function ran. Every summary is built from the envelope the tool actually returned — if a
 * count is not in there, it is not in the headline.
 */
export function toolSummary(call: ToolCall): string {
  const label = TOOL_LABELS[call.name] ?? call.name.replace(/_/g, ' ')
  if (call.running) return `${label}…`

  const data = call.envelope?.data ?? {}
  const detail = detailFor(call.name, data)
  return detail ? `${label} · ${detail}` : label
}

const TOOL_LABELS: Record<string, string> = {
  live_li: 'Checked L&I live',
  live_opa: 'Checked OPA live',
  live_rtt: 'Checked the deed index live',
  live_sheriff: 'Checked the sheriff’s site live',
  get_parcel: 'Read the parcel',
  get_verdict: 'Computed the verdict',
  get_zoning: 'Read the zoning',
  get_comps: 'Pulled comps',
  get_violations: 'Read violations',
  get_delinquency: 'Read the tax record',
  get_deed_chain: 'Read the deed chain',
  get_neighbors: 'Looked at the neighbours',
  screen_sale: 'Screened the sale',
  screen_parcels: 'Screened lots',
  compute_deal: 'Ran the deal',
  add_to_pipeline: 'Added to the pipeline',
  watch: 'Started watching',
  draft_loi: 'Drafted an LOI',
  draft_letter: 'Drafted a letter',
  export_csv: 'Exported a CSV',
  remember: 'Remembered that',
}

function count(value: unknown): number | null {
  return Array.isArray(value) ? value.length : null
}

function detailFor(name: string, data: Record<string, unknown>): string | null {
  if (name.startsWith('live_')) {
    const diff = count(data.diff)
    if (diff === null) return null
    return diff === 0 ? 'agrees with our copy' : `${diff} differ`
  }
  if (name === 'screen_sale' || name === 'screen_parcels') {
    const summary = data.summary as Record<string, unknown> | undefined
    const screened = (data.screened as number) ?? (summary?.screened as number)
    const bid = (data.bid as number) ?? (summary?.BID as number) ?? (summary?.bid as number)
    if (typeof screened === 'number' && typeof bid === 'number') {
      return `${screened} lots · ${bid} BID`
    }
    if (typeof screened === 'number') return `${screened} lots`
    return null
  }
  if (name === 'add_to_pipeline' && typeof data.parcel_number === 'string') {
    return String(data.address ?? data.parcel_number)
  }
  if (name === 'export_csv' && typeof data.rows === 'number') {
    return `${data.rows} rows`
  }
  const unverified = count(data.unverified)
  return unverified && unverified > 0 ? `${unverified} unverified` : null
}

/** A source is internal when it points at a lot we can open in the drawer. */
export function internalParcel(url: string | null | undefined): string | null {
  if (!url) return null
  const match = /atlas\.phila\.gov\/(?:phl:)?([0-9]{6,12})/.exec(url)
  return match ? `phl:${match[1]}` : null
}
