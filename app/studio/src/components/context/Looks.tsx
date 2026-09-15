import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getLook, getLooks, type LookRow, type LooksResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Pill } from '@/components/ui/pill'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

type LookDetail = Awaited<ReturnType<typeof getLook>>

const HEADING = 'text-xs font-medium uppercase tracking-wide text-muted'
const MEDIUM_GLYPHS: Record<LookRow['medium'], string> = { image: '▣' }

function LookGrid({
  query,
  selected,
  onSelect,
}: {
  query: UseQueryResult<LooksResponse>
  selected: string | null
  onSelect: (name: string) => void
}) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const looks = query.data.looks
  if (looks.length === 0) return <Empty>definitions/looks/ is empty</Empty>
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {looks.map((look) => (
        <button
          key={look.name}
          type="button"
          aria-pressed={look.name === selected}
          onClick={() => onSelect(look.name)}
          className={cn(
            'flex flex-col items-start gap-1 rounded-lg border border-line bg-paper p-2 text-left transition-colors hover:bg-wash',
            look.name === selected && 'bg-wash ring-1 ring-ink',
          )}
          data-testid="look-card"
          data-name={look.name}
        >
          <span className="w-full truncate text-sm font-medium text-ink">{look.name}</span>
          <span className="text-xs text-muted">
            {MEDIUM_GLYPHS[look.medium]} {look.ratio}
          </span>
        </button>
      ))}
    </div>
  )
}

function LookDetailBody({ selected, query }: { selected: string | null; query: UseQueryResult<LookDetail> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (selected === null) return <Empty>no look selected</Empty>
  if (!query.data) return <Loading />
  const look = query.data
  return (
    <div className="space-y-1 border-t border-line pt-3 text-sm" data-testid="look-detail" data-name={look.name}>
      <p className="flex flex-wrap items-baseline gap-x-2 text-muted">
        <span className="font-medium text-ink">{look.name}</span>
        <span>·</span>
        <span className="min-w-0" data-testid="look-slots">
          slots: {look.slots.length === 0 ? '—' : look.slots.join(' ')}
        </span>
        <span>·</span>
        <span>
          {look.limits_measured === null ? 'limits not measured' : `limits measured ${shortDate(look.limits_measured.slice(0, 10))}`}
        </span>
      </p>
      <p className="flex flex-wrap items-baseline gap-x-2 text-muted">
        <span>used by {num(look.used_by)} assets</span>
        <span>·</span>
        <span>build cost {look.build_cost ?? '—'}</span>
        <span>·</span>
        <a href={look.layouts} target="_blank" rel="noreferrer" className="text-ink hover:underline" data-testid="look-layouts-link">
          layouts.md ↗
        </a>
      </p>
    </div>
  )
}

export function LooksPanel() {
  const looks = useQuery({ queryKey: ['looks'], queryFn: getLooks })
  const [picked, setPicked] = useState<string | null>(null)
  const rows = looks.data?.looks ?? []
  const selected = picked ?? rows[0]?.name ?? null
  const look = useQuery({
    queryKey: ['look', selected],
    queryFn: () => getLook(selected as string),
    enabled: selected !== null,
  })
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="looks-panel"
      data-state={looks.isPending ? 'loading' : looks.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
        <h2 className={HEADING}>Looks</h2>
        <span className="text-xs text-muted">
          {looks.data ? `${num(rows.length)} image · ` : ''}definitions/looks/
        </span>
      </div>
      <LookGrid query={looks} selected={selected} onSelect={setPicked} />
      <LookDetailBody selected={selected} query={look} />
    </Card>
  )
}
