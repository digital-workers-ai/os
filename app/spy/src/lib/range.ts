import { shortDate } from '@/lib/format'

export const PRESETS = ['last7', 'last30', 'last90', 'custom'] as const

export type Preset = (typeof PRESETS)[number]

export const PRESET_LABELS: Record<Preset, string> = {
  last7: 'Last 7 days',
  last30: 'Last 30 days',
  last90: 'Last 90 days',
  custom: 'Custom',
}

const DAYS: Record<Exclude<Preset, 'custom'>, number> = { last7: 7, last30: 30, last90: 90 }

export interface Bounds {
  from: string
  to: string
}

export type Range = { preset: Exclude<Preset, 'custom'> } | ({ preset: 'custom' } & Bounds)

export const DEFAULT_RANGE: Range = { preset: 'last30' }

export function shiftDays(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export const bounds = (range: Range, today: string): Bounds =>
  range.preset === 'custom' ? { from: range.from, to: range.to } : { from: shiftDays(today, 1 - DAYS[range.preset]), to: today }

export const previousLabel = (from: string, to: string) => `previous ${shortDate(from)} – ${shortDate(to)}`
