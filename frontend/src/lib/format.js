const currencyFormatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
});
export function formatCurrency(value) {
    if (value == null)
        return '—';
    return currencyFormatter.format(value);
}
export function formatRange(low, high) {
    if (low == null || high == null)
        return '—';
    return `${formatCurrency(low)} – ${formatCurrency(high)}`;
}
