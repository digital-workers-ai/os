export const num = (n: number) => n.toLocaleString()

export const percent = (share: number) => `${Math.round(share * 100)}%`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function shortDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-')
  const name = month ? MONTHS[Number(month) - 1] : undefined
  if (!name) return iso
  return day ? `${name} ${Number(day)}` : `${name} ${year}`
}

const UNITS: [string, number][] = [
  ['d', 86_400_000],
  ['h', 3_600_000],
  ['min', 60_000],
]

export function relative(iso: string, now = Date.now()): string {
  const elapsed = now - Date.parse(iso)
  for (const [unit, ms] of UNITS) if (elapsed >= ms) return `${Math.floor(elapsed / ms)} ${unit} ago`
  return 'just now'
}
