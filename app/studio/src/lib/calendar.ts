import type { CalendarResponse, Kind, Slot, SlotState } from '@/api'

const KIND_GLYPHS: Record<Kind, string> = {
  post: 'in',
  newsletter: '✉',
  blog: '¶',
  image: '▣',
  video: '▶',
  ad: '▣',
}

const STATE_MARKS: Record<SlotState, string> = {
  built: '✓',
  approved: '◑',
  proposed: '◔',
  empty: '○',
  skipped: '⊘',
}

const STATE_TONES: Record<SlotState, string> = {
  built: 'text-ok',
  approved: 'text-ok',
  proposed: 'text-ink',
  empty: 'text-muted',
  skipped: 'text-muted',
}

export const kindGlyph = (kind: string) => KIND_GLYPHS[kind as Kind] ?? '•'

export const stateMark = (state: string) => STATE_MARKS[state as SlotState] ?? '○'

export const stateTone = (state: string) => STATE_TONES[state as SlotState] ?? 'text-muted'

export const LEGEND: { mark: string; label: string }[] = [
  { mark: '✓', label: 'built' },
  { mark: '◔', label: 'proposed' },
  { mark: '○', label: 'empty' },
  { mark: '!', label: 'reactive' },
]

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad = (n: number) => String(n).padStart(2, '0')

export const iso = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

export const parseDay = (day: string) => {
  const [year, month, date] = day.split('-').map(Number)
  return new Date(year || 1970, (month || 1) - 1, date || 1)
}

export const todayIso = () => iso(new Date())

export const addDays = (day: string, days: number) => {
  const date = parseDay(day)
  date.setDate(date.getDate() + days)
  return iso(date)
}

export const addMonths = (day: string, months: number) => {
  const date = parseDay(day)
  return iso(new Date(date.getFullYear(), date.getMonth() + months, 1))
}

export const weekStart = (day: string) => {
  const date = parseDay(day)
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return iso(date)
}

export const monthStart = (day: string) => {
  const date = parseDay(day)
  return iso(new Date(date.getFullYear(), date.getMonth(), 1))
}

export const monthEnd = (day: string) => {
  const date = parseDay(day)
  return iso(new Date(date.getFullYear(), date.getMonth() + 1, 0))
}

export const monthLabel = (day: string) => {
  const date = parseDay(day)
  return `${MONTHS[date.getMonth()]} ${date.getFullYear()}`
}

export const weekLabel = (day: string) => {
  const start = weekStart(day)
  const end = addDays(start, 6)
  return `${dayLabel(start)} – ${dayLabel(end)} ${SHORT_MONTHS[parseDay(end).getMonth()]}`
}

export function dayLabel(day: string) {
  const date = parseDay(day)
  return `${WEEKDAYS[(date.getDay() + 6) % 7]} ${date.getDate()}`
}

export const dayMonth = (day: string) => `${dayLabel(day)} ${SHORT_MONTHS[parseDay(day).getMonth()]}`

export const weekday = (day: string) => WEEKDAYS[(parseDay(day).getDay() + 6) % 7]

export const sameMonth = (day: string, anchor: string) => day.slice(0, 7) === anchor.slice(0, 7)

export function monthGrid(anchor: string) {
  const end = monthEnd(anchor)
  const days: string[] = []
  let cursor = weekStart(monthStart(anchor))
  while (cursor <= end || days.length % 7 !== 0) {
    days.push(cursor)
    cursor = addDays(cursor, 1)
  }
  return days
}

export const weekDays = (anchor: string) => {
  const start = weekStart(anchor)
  return WEEKDAYS.map((_, index) => addDays(start, index))
}

export const byDate = (slots: Slot[]) => {
  const map = new Map<string, Slot[]>()
  for (const slot of slots) map.set(slot.date, [...(map.get(slot.date) ?? []), slot])
  return map
}

export const slotKey = (slot: Slot) => `${slot.date}|${slot.name}`

export const slotTime = (slot: Slot) => {
  for (const line of slot.spec) {
    const found = line.match(/\b(?:at|time)\s*:\s*(\d{1,2}):(\d{2})\b/)
    if (found) return `${pad(Number(found[1]))}:${found[2]}`
  }
  return null
}

export const cadenceLine = (cadence: CalendarResponse['cadence']) =>
  cadence.map((entry) => `${entry.kind}s ${entry.done} of ${entry.planned}`).join(' · ')

export const hhmm = (stamp: string) => (stamp.length >= 16 && stamp[10] === 'T' ? stamp.slice(11, 16) : stamp)

export const since = (stamp: string) => {
  const started = new Date(stamp).getTime()
  if (Number.isNaN(started)) return stamp
  const seconds = Math.max(0, Math.round((Date.now() - started) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${pad(seconds % 60)}s`
  return `${Math.floor(minutes / 60)}h ${pad(minutes % 60)}m`
}
