export const num = (n: number) => n.toLocaleString()

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

export const short = (s: string, n = 8) => (s.length > n ? `${s.slice(0, n)}…` : s)

export const anchorText = (anchor: string) => anchor.split('|').join('@')

export function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86400)}d ago`
}

export function when(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'never'
  return d.toDateString() === new Date().toDateString()
    ? relTime(iso)
    : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
