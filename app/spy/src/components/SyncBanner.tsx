import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, RefreshCw, TriangleAlert } from 'lucide-react'
import { asApiError, getSources, rebuild, syncSources } from '@/api'
import { Button } from '@/components/ui/button'
import { timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'

type Step = 'idle' | 'syncing' | 'rebuilding'

const LABELS: Record<Step, string> = { idle: 'Sync now', syncing: 'Syncing…', rebuilding: 'Rebuilding…' }

export function SyncBanner({ source }: { source: string }) {
  const queryClient = useQueryClient()
  const sources = useQuery({ queryKey: ['sources'], queryFn: getSources, refetchInterval: 60_000 })
  const [step, setStep] = useState<Step>('idle')
  const [failure, setFailure] = useState<string | null>(null)

  if (!sources.data) return null

  const latest = sources.data.sources.find((row) => row.source === source)?.last_success ?? null
  const busy = step !== 'idle'
  const failed = failure !== null

  async function syncNow() {
    setStep('syncing')
    try {
      await syncSources([source])
      setStep('rebuilding')
      await rebuild()
      setFailure(null)
      void queryClient.invalidateQueries()
    } catch (e) {
      setFailure(asApiError(e).detail)
    } finally {
      setStep('idle')
    }
  }

  return (
    <div
      role={failed ? 'alert' : 'status'}
      className={cn(
        'mb-4 flex items-center justify-between gap-2 rounded-lg border px-3 py-1 text-sm',
        failed ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-line bg-wash text-muted',
      )}
      data-testid="sync-banner"
    >
      <div className="flex min-w-0 items-center gap-2">
        {failed ? <TriangleAlert size={16} className="shrink-0" /> : <CircleCheck size={16} className="shrink-0" />}
        <span data-testid="sync-banner-text">
          {failed ? `Sync failed: ${failure}` : latest ? `Last sync: ${timeAgo(latest, sources.dataUpdatedAt)}.` : 'Never synced.'}
        </span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="[&_svg]:size-3"
        onClick={syncNow}
        disabled={busy}
        aria-busy={busy || undefined}
        data-testid="sync-now"
      >
        <RefreshCw className={cn(busy && 'animate-spin')} />
        {LABELS[step]}
      </Button>
    </div>
  )
}
