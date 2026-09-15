import { shortDate } from '@/lib/format'

export const stamp = (at: string) => {
  const [day, time] = at.split(/[T ]/)
  return time ? `${shortDate(day)} ${time.slice(0, 5)}` : shortDate(day)
}
