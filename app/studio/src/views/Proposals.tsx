import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { asApiError, getProposals, type Kind, type ProposalRow, type ProposalStatus } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { dayLabel, kindGlyph } from '@/lib/calendar'
import { cn } from '@/lib/utils'

const STATUSES: ProposalStatus[] = ['open', 'approved', 'rejected', 'built']
const KINDS: Kind[] = ['post', 'newsletter', 'blog', 'image', 'ad']
const SELECT =
  'h-8 rounded-md border border-input bg-transparent px-2 text-xs text-ink transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'

const slotLabel = (row: ProposalRow) => (row.slot_date === null ? 'reactive' : `slot ${dayLabel(row.slot_date)}`)

function Row({ row }: { row: ProposalRow }) {
  const claimed = row.claims_total > 0
  const verified = claimed && row.claims_verified === row.claims_total
  return (
    <div className="border-b border-line/30 px-1 py-3 last:border-0" data-testid="proposal-row" data-seq={row.seq} data-kind={row.kind}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Mono className="text-muted">#{row.seq}</Mono>
        <span className="whitespace-nowrap text-muted">
          {kindGlyph(row.kind)} {row.kind}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium text-ink">{row.title}</span>
        <span className="whitespace-nowrap text-xs text-muted">{slotLabel(row)}</span>
        <Mono className="whitespace-nowrap text-muted">{row.skill}</Mono>
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-muted">
        <span className="min-w-0 flex-1">
          evidence: {row.evidence_summary || 'none recorded'}
          {claimed && (
            <>
              {' · '}
              <span className="whitespace-nowrap" data-testid="proposal-claims">
                claims {row.claims_verified}/{row.claims_total} <span className={verified ? 'text-ok' : 'text-down'}>{verified ? '✓' : '⚠'}</span>
              </span>
            </>
          )}
        </span>
        <Link
          to={`/proposals/${row.seq}`}
          className={buttonVariants({ variant: 'outline', size: 'sm', className: 'h-7 px-2' })}
          data-testid="proposal-open-btn"
        >
          Open
        </Link>
      </div>
    </div>
  )
}

export function Proposals() {
  const [status, setStatus] = useState<ProposalStatus>('open')
  const [kind, setKind] = useState('')
  const [slot, setSlot] = useState('')
  const query = useQuery({ queryKey: ['proposals', status, kind], queryFn: () => getProposals(status, kind || undefined) })
  const data = query.data
  const rows = data?.proposals ?? []
  const slotNames = [...new Set(rows.map((row) => row.slot_name).filter((name): name is string => name !== null))].sort()
  const shown = rows.filter((row) => slot === '' || (slot === 'reactive' ? row.slot_date === null : row.slot_name === slot))

  return (
    <div className="space-y-4" data-testid="proposals-view" data-status={status} data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="proposal status">
          {STATUSES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={status === option}
              onClick={() => setStatus(option)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                status === option ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink',
              )}
              data-testid={`proposals-tab-${option}`}
            >
              {option}
              {data && <span className="ml-1 tabular-nums opacity-70">{data.counts[option] ?? 0}</span>}
            </button>
          ))}
        </div>
        <select value={kind} onChange={(event) => setKind(event.target.value)} className={SELECT} aria-label="kind" data-testid="proposals-kind-filter">
          <option value="">every kind</option>
          {KINDS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <select value={slot} onChange={(event) => setSlot(event.target.value)} className={SELECT} aria-label="slot" data-testid="proposals-slot-filter">
          <option value="">every slot</option>
          <option value="reactive">reactive</option>
          {slotNames.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      {query.error && <ErrorBanner error={asApiError(query.error)} testId="proposals-error" />}
      {!data && !query.error && <Loading />}

      {data && (
        <Card className="p-3 sm:p-4">
          {shown.length === 0 ? (
            <Empty testId="proposals-empty">
              {rows.length === 0 ? `nothing ${status} — the marketer proposes, you decide` : 'no proposal matches these filters'}
            </Empty>
          ) : (
            shown.map((row) => <Row key={row.seq} row={row} />)
          )}
          <p className="mt-3 border-t border-line pt-2 text-xs text-muted" data-testid="proposals-footer">
            approve → the backend builds it · reject → a reason the taste agent reads
          </p>
        </Card>
      )}
    </div>
  )
}
