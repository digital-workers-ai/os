import type { Kind, Slot, SlotState } from '@/api'
import { shortDate } from '@/lib/format'

export type Mode = 'month' | 'week' | 'list'

export const MODES: Mode[] = ['month', 'week', 'list']

export const MODE_LABELS: Record<Mode, string> = { month: 'Month', week: 'Week', list: 'List' }

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

const GLYPHS: Record<Kind, string> = { post: '✎', newsletter: '✉', blog: '¶', image: '▣', carousel: '▤' }

const MARKS: Record<SlotState, string> = { built: '●', empty: '○', skipped: '×' }

export const MARK_LABELS: [SlotState, string][] = [
  ['built', 'built'],
  ['empty', 'empty'],
  ['skipped', 'skipped'],
]

const pad = (n: number) => String(n).padStart(2, '0')

const iso = (year: number, month: number, day: number) => `${year}-${pad(month)}-${pad(day)}`

const parts = (date: string) => date.split('-').map(Number) as [number, number, number]

export function todayIso(): string {
  const now = new Date()
  return iso(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

export function addDays(date: string, days: number): string {
  const [year, month, day] = parts(date)
  const shifted = new Date(Date.UTC(year, month - 1, day + days))
  return iso(shifted.getUTCFullYear(), shifted.getUTCMonth() + 1, shifted.getUTCDate())
}

export function addMonths(date: string, months: number): string {
  const [year, month] = parts(date)
  const shifted = new Date(Date.UTC(year, month - 1 + months, 1))
  return iso(shifted.getUTCFullYear(), shifted.getUTCMonth() + 1, 1)
}

export const monthStart = (date: string) => `${date.slice(0, 7)}-01`

export const monthEnd = (date: string) => addDays(addMonths(date, 1), -1)

export function dayOfWeek(date: string): number {
  const [year, month, day] = parts(date)
  return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7
}

export const weekday = (date: string) => WEEKDAYS[dayOfWeek(date)]

export const weekStart = (date: string) => addDays(date, -dayOfWeek(date))

export const weekDays = (date: string): string[] => {
  const start = weekStart(date)
  return Array.from({ length: 7 }, (_, i) => addDays(start, i))
}

export function monthGrid(date: string): string[][] {
  const end = monthEnd(date)
  const rows: string[][] = []
  let cursor = weekStart(monthStart(date))
  while (cursor <= end) {
    rows.push(weekDays(cursor))
    cursor = addDays(cursor, 7)
  }
  return rows
}

export const monthLabel = (date: string) => {
  const [year, month] = parts(date)
  return `${MONTHS[month - 1]} ${year}`
}

export const weekLabel = (date: string) => {
  const days = weekDays(date)
  return `${shortDate(days[0])} – ${shortDate(days[6])}, ${days[6].slice(0, 4)}`
}

export const rangeLabel = (mode: Mode, anchor: string) => (mode === 'week' ? weekLabel(anchor) : monthLabel(anchor))

export function calendarRange(mode: Mode, anchor: string): { from: string; to: string } {
  if (mode === 'week') {
    const days = weekDays(anchor)
    return { from: days[0], to: days[6] }
  }
  if (mode === 'list') return { from: monthStart(anchor), to: monthEnd(anchor) }
  const grid = monthGrid(anchor)
  return { from: grid[0][0], to: grid[grid.length - 1][6] }
}

export const step = (mode: Mode, anchor: string, direction: 1 | -1) =>
  mode === 'week' ? addDays(anchor, 7 * direction) : addMonths(anchor, direction)

export const sortSlots = (slots: Slot[]) => [...slots].sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))

export function slotsByDate(slots: Slot[]): Map<string, Slot[]> {
  const groups = new Map<string, Slot[]>()
  for (const slot of sortSlots(slots)) groups.set(slot.date, [...(groups.get(slot.date) ?? []), slot])
  return groups
}

export const hhmm = (timestamp: string) => timestamp.slice(11, 16)

export const since = (timestamp: string) => `since ${hhmm(timestamp)}`

export const kindGlyph = (kind: Kind) => GLYPHS[kind]

export const stateMark = (state: SlotState) => MARKS[state]
