/**
 * Where a fact on the Lot page came from, and whether the reader can open it.
 *
 * Mirrors the URL shapes the backend's agent/tools/urls.py builds, so a "Show me" in the
 * UI and a source in an Analyst envelope point at the same place. Where no public URL can
 * be constructed the answer is the stored source and its as-of date — that is honest, and
 * a dead link pretending otherwise is not.
 */

export type ShowMeTarget =
  | { kind: 'external'; label: string; url: string }
  | { kind: 'provision'; label: string; provisionId: string }
  | { kind: 'stored'; label: string; source: string; asOf: string | null }

const ATLAS = 'https://atlas.phila.gov'
const LI_SEARCH = 'https://li.phila.gov/property-history/search?address='
const CIVILVIEW = 'https://philadelphia.sheriffsale.com/'
const CARTO = 'https://phl.carto.com/api/v2/sql?q='

export function localKey(parcelNumber: string): string {
  return parcelNumber.split(':').pop() ?? parcelNumber
}

export function atlasUrl(parcelNumber: string): string {
  return `${ATLAS}/${encodeURIComponent(localKey(parcelNumber))}`
}

/**
 * The Recorder publishes deeds by document id; Atlas shows the same parcel's deed list.
 * Atlas is the link we can build reliably, so that is the one offered.
 */
export function deedTarget(parcelNumber: string, documentId: string | null): ShowMeTarget {
  if (!documentId) {
    return { kind: 'stored', label: 'Show me', source: 'rtt_summary', asOf: null }
  }
  return {
    kind: 'external',
    label: `Deed ${documentId}`,
    url: `${atlasUrl(parcelNumber)}#deeds`,
  }
}

export function violationTarget(address: string | null): ShowMeTarget {
  if (!address) {
    return { kind: 'stored', label: 'Show me', source: 'li_violations', asOf: null }
  }
  return {
    kind: 'external',
    label: 'L&I property history',
    url: `${LI_SEARCH}${encodeURIComponent(address)}`,
  }
}

export function sheriffTarget(): ShowMeTarget {
  return { kind: 'external', label: "Sheriff's listing", url: CIVILVIEW }
}

export function provisionTarget(provisionId: string | null, cite: string | null): ShowMeTarget {
  if (!provisionId) {
    return { kind: 'stored', label: 'Show me', source: 'philadelphia_code', asOf: null }
  }
  return { kind: 'provision', label: cite ?? provisionId, provisionId }
}

export function cartoTarget(table: string, parcelNumber: string): ShowMeTarget {
  const sql = `SELECT * FROM ${table} WHERE parcel_number = '${localKey(parcelNumber)}'`
  return { kind: 'external', label: `${table} row`, url: `${CARTO}${encodeURIComponent(sql)}` }
}

export function storedTarget(source: string, asOf: string | null): ShowMeTarget {
  return { kind: 'stored', label: 'Show me', source, asOf }
}
