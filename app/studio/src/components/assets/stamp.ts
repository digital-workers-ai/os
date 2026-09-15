import { shortDate } from '@/lib/format'

export const stampLabel = (iso: string) => {
  const [day, time] = iso.split(/[T ]/)
  return time ? `${shortDate(day)} ${time.slice(0, 5)}` : shortDate(day)
}

export const durationLabel = (ms: number) => {
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}
