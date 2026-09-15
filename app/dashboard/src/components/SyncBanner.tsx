import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, RefreshCw, TriangleAlert } from 'lucide-react'
import { asApiError, getSources, rebuild, sync, type MetricResponse } from '@/api'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function timeAgo(from: number, to: number): string {
  const mins = Math.floor((to - from) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export function pageSources(responses: (MetricResponse | undefined)[]): string[] | null {
  const names = new Set(responses.flatMap((r) => r?.raw_fields ?? []).map((field) => field.split('.')[0]))
  return names.size ? [...names].sort() : null
}

type Phase = 'idle' | 'syncing' | 'rebuilding'

const LABEL: Record<Phase, string> = { idle: 'Sync now', syncing: 'Syncing…', rebuilding: 'Rebuilding…' }

export function SyncBanner({ sources }: { sources: string[] | null }) {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['sources'], queryFn: getSources, refetchInterval: 60_000 })
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)

  if (!status.data) return null

  const covered = sources ? status.data.sources.filter((s) => sources.includes(s.source)) : status.data.sources
  const successes = covered.flatMap((s) => (s.last_success ? [Date.parse(s.last_success)] : []))
  const latest = successes.length ? Math.max(...successes) : null
  const busy = phase !== 'idle'
  const Icon = error ? TriangleAlert : CircleCheck
  const text = error ? `Sync failed: ${error}` : latest === null ? 'Never synced.' : `Last sync: ${timeAgo(latest, status.dataUpdatedAt)}.`

  async function run() {
    setPhase('syncing')
    try {
      await sync(sources)
      setPhase('rebuilding')
      await rebuild()
    } catch (e) {
      setError(asApiError(e).detail)
      setPhase('idle')
      return
    }
    setError(null)
    setPhase('idle')
    await queryClient.invalidateQueries()
  }

  return (
    <div
      role={error ? 'alert' : 'status'}
      className={cn(
        'mb-4 flex items-center justify-between gap-2 rounded-lg border px-3 py-1.5 text-sm md:px-4',
        error ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-line bg-wash text-muted',
      )}
      data-testid="sync-banner"
    >
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={16} className="shrink-0" />
        <span data-testid="sync-banner-text">{text}</span>
      </div>
      <Button variant="ghost" size="sm" className="h-7 px-2" onClick={run} disabled={busy} aria-busy={busy} data-testid="sync-now">
        <RefreshCw className={cn(busy && 'animate-spin')} />
        {LABEL[phase]}
      </Button>
    </div>
  )
}
