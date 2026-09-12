export const num = (n: number) => n.toLocaleString()

export const fixed = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const compact = (n: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export const delta = (value: number | null, previous: number | null) =>
  value === null || !previous ? null : (value - previous) / previous

export const pct = (d: number) => `${(Math.round(Math.abs(d) * 1000) / 10).toLocaleString()}%`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function shortDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  const name = month ? MONTHS[Number(month) - 1] : undefined
  if (!name) return iso
  return day ? `${name} ${Number(day)}` : `${name} ${year}`
}
