import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill, type Tone } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { anchorText, num } from '@/lib/format'
import { cn } from '@/lib/utils'
import { BODY, FULL, useLoad } from '../inference/shared'

type Status = 'pending' | 'confirmed' | 'rejected'
type Action = 'confirm' | 'reject' | 'unmerge'

interface Side {
  anchor: string
  label: string
}

interface Candidate {
  seq: number
  entity_type: string
  left: Side
  right: Side
  score: number
  status: Status
  evidence_holds: boolean
  evidence: { attr: string; left_value: string }[]
}

interface CandidatesResponse {
  candidates: Candidate[]
  counts: Record<Status, number>
}

const STATUSES: Status[] = ['pending', 'confirmed', 'rejected']
const TONE: Record<Status, Tone> = { pending: 'neutral', confirmed: 'ok', rejected: 'err' }
const KEY = 'font-medium text-ink'
const NUM = 'text-right tabular-nums'
const TOP = 'align-top'
const NOTICE = 'mt-2 -mb-1'

export function Review() {
  const [status, setStatus] = useState<string>('pending')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<ApiError | null>(null)
  const list = useLoad(() => get<CandidatesResponse>(`/api/resolution/candidates?status=${status || 'all'}&limit=200`), [status])
  const counts = list.data?.counts
  const total = STATUSES.reduce((n, s) => n + (counts?.[s] ?? 0), 0)
  const rows = list.data?.candidates ?? []

  const act = async (seq: number, action: Action) => {
    setBusy(true)
    setActionError(null)
    try {
      await post(`/api/resolution/candidates/${seq}/${action}`)
      list.reload()
    } catch (e) {
      setActionError(asApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const button = (seq: number, action: Action, label: string, outline = false) => (
    <Button size="sm" variant={outline ? 'outline' : 'default'} disabled={busy} onClick={() => act(seq, action)} data-testid={`review-${action}`}>
      {label}
    </Button>
  )

  return (
    <SectionCard
      testId="review"
      title={
        <Filter
          value={status}
          onChange={setStatus}
          all={`all (${num(total)})`}
          options={STATUSES.map((s) => [s, counts?.[s] ?? 0])}
          testId="review-status-filter"
        />
      }
      description={
        actionError &&
        (actionError.status === 409 ? (
          <Banner className={NOTICE} testId="review-error">
            <Mono>409</Mono> {actionError.detail}
          </Banner>
        ) : (
          <ErrorBanner error={actionError} className={NOTICE} testId="review-error" />
        ))
      }
      className={FULL}
      bodyClassName={BODY}
    >
      <ErrorBanner error={list.error} className="mb-3" />
      {list.loading && <Loading />}
      {list.data && rows.length === 0 && <Empty>no pairs to review</Empty>}
      {rows.length > 0 && (
        <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="review-table">
          <TableHeader className={STICKY_HEAD}>
            <TableRow>
              <TableHead hint="Two records that may be one person">Pair ({num(rows.length)})</TableHead>
              <TableHead className="w-24" hint="What kind of thing both records are">Entity</TableHead>
              <TableHead className="w-56" hint="What the two records agree on">Evidence</TableHead>
              <TableHead className={cn(NUM, 'w-20')} hint="How alike the two names are, 0 to 1">Score</TableHead>
              <TableHead className="w-44" hint="Pending, confirmed, or rejected">Status</TableHead>
              <TableHead className="w-36" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.seq} data-testid="review-row" data-seq={c.seq}>
                <TableCell className={TOP}>
                  <span className={cn(KEY, 'block')}>{c.left.label}</span>
                  <span className={cn(KEY, 'block')}>{c.right.label}</span>
                  <Mono>
                    {anchorText(c.left.anchor)} · {anchorText(c.right.anchor)}
                  </Mono>
                </TableCell>
                <TableCell className={TOP}>
                  <Pill>{c.entity_type}</Pill>
                </TableCell>
                <TableCell className={TOP}>
                  <span className="flex flex-col items-start gap-1">
                    {c.evidence.map((e) => (
                      <Chip key={e.attr}>
                        {e.attr}=<strong>{e.attr === 'name' ? c.score.toFixed(2) : e.left_value}</strong>
                      </Chip>
                    ))}
                  </span>
                </TableCell>
                <TableCell className={cn(NUM, TOP)}>{c.score.toFixed(2)}</TableCell>
                <TableCell className={TOP}>
                  <span className="inline-flex flex-wrap gap-1">
                    <Pill tone={TONE[c.status]}>{c.status}</Pill>
                    {c.status === 'confirmed' && !c.evidence_holds && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span tabIndex={0} data-testid="review-evidence-gone" className="inline-flex focus-visible:outline-none">
                            <Pill tone="warn">evidence gone</Pill>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-xs">
                          A person confirmed this pair, but the two records no longer share any evidence. Check it again; unmerge if it was wrong.
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </span>
                </TableCell>
                <TableCell className={cn('pr-0 text-right', TOP)}>
                  <span className="inline-flex gap-2">
                    {c.status !== 'confirmed' && button(c.seq, 'confirm', 'Confirm')}
                    {c.status === 'pending' && button(c.seq, 'reject', 'Reject', true)}
                    {c.status === 'confirmed' && button(c.seq, 'unmerge', 'Unmerge', true)}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}
