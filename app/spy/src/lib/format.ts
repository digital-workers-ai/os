export const num = (n: number) => n.toLocaleString()

export const percent = (share: number) => `${Math.round(share * 100)}%`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function shortDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-')
  const name = month ? MONTHS[Number(month) - 1] : undefined
  if (!name) return iso
  return day ? `${name} ${Number(day)}` : `${name} ${year}`
}

const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? '' : 's'} ago`

export function timeAgo(iso: string, now = Date.now()): string {
  const mins = Math.floor((now - Date.parse(iso)) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return plural(mins, 'minute')
  const hours = Math.floor(mins / 60)
  if (hours < 24) return plural(hours, 'hour')
  return plural(Math.floor(hours / 24), 'day')
}
