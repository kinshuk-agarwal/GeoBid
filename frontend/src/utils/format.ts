const intFmt = new Intl.NumberFormat('en-IN')
const inrFmt = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export const formatNumber = (n: number) => intFmt.format(n)
export const formatINR = (n: number) => inrFmt.format(n)
/** ₹12,000–13,000 */
export const formatINRRange = (low: number, high: number) => `${inrFmt.format(low)}–${intFmt.format(high)}`
/** Compact: ₹12k–13k, ₹6k–6.5k */
export const formatINRRangeShort = (low: number, high: number) => {
  const k = (n: number) => (n >= 1000 ? `${+(n / 1000).toFixed(1)}k` : String(n))
  return `₹${k(low)}–${k(high)}`
}
// Footfall is an estimate, so it is shown as a rounded band, never an exact
// count. Bands are fixed per order of magnitude (half of the leading power of
// ten), so they never overlap: 61 -> "60–65", 128 -> "100–150",
// 1,254 -> "1,000–1,500", 11,690 -> "10,000–15,000".
export function footfallRange(n: number): string {
  if (n <= 0) return '0'
  if (n < 10) return 'under 10'
  const step = 10 ** Math.floor(Math.log10(n)) / 2
  const low = Math.floor(n / step) * step
  return `${intFmt.format(low)}–${intFmt.format(low + step)}`
}

export const formatKm = (n: number) => `${n < 10 ? n.toFixed(1) : Math.round(n)} km`
