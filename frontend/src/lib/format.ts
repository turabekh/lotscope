const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '—'
  return currencyFormatter.format(value)
}

export function formatRange(low: number | null | undefined, high: number | null | undefined): string {
  if (low == null || high == null) return '—'
  return `${formatCurrency(low)} – ${formatCurrency(high)}`
}
