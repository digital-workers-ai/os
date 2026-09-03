import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, type ApiError } from '../../api'
import { cn } from '@/lib/utils'

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setData(null)
    setError(null)
    load()
      .then((d) => {
        if (live) setData(d)
      })
      .catch((e) => {
        if (live) setError(asApiError(e))
      })
    return () => {
      live = false
    }
  }, [...deps, tick])
  return { data, error, loading: data === null && error === null, reload: () => setTick((t) => t + 1) }
}

export type Tone = 'up' | 'warn' | 'err' | 'neutral'

const tones: Record<Tone, string> = {
  up: 'bg-dbb-up/10 text-dbb-up',
  warn: 'bg-amber-50 text-amber-800',
  err: 'bg-dbb-clay/10 text-dbb-clay',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

export function Pill({ tone = 'neutral', className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium', tones[tone], className)}>
      {children}
    </span>
  )
}

export function Chip({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 rounded-full bg-dbb-sand px-2.5 py-0.5 text-xs text-dbb-muted [&_strong]:font-medium [&_strong]:text-dbb-charcoal"
    >
      {children}
    </span>
  )
}

export function Mono({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <span title={title} className="font-mono text-xs">
      {children}
    </span>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-dbb-muted">{children}</p>
}

export function Fail({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <div role="alert" className="rounded-lg border border-dbb-clay/30 bg-dbb-clay/5 px-3 py-2 text-sm text-dbb-clay">
      <Mono>{error.status || 'network'}</Mono> {error.detail}
    </div>
  )
}

export function LayerOff({ error }: { error: ApiError | null }) {
  if (!error) return null
  if (error.status !== 409) return <Fail error={error} />
  return (
    <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      {error.detail}
    </div>
  )
}

export function Enabled({ on }: { on: boolean }) {
  return <Pill tone={on ? 'up' : 'warn'}>{on ? 'enabled' : 'disabled'}</Pill>
}

export const ALL = '*'

export const short = (s: string) => s.slice(0, 12)

export const num = (n: number) => n.toLocaleString()

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
