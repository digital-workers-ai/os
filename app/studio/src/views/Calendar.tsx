import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { asApiError, fillCalendar, getCalendar, redoProposal, skipSlot, type Slot } from '@/api'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import {
  addDays,
  addMonths,
  byDate,
  cadenceLine,
  dayLabel,
  kindGlyph,
  LEGEND,
  monthGrid,
  monthLabel,
  sameMonth,
  slotKey,
  slotTime,
  stateMark,
  stateTone,
  todayIso,
  WEEKDAYS,
  weekDays,
  weekLabel,
} from '@/lib/calendar'
import { cn } from '@/lib/utils'

type ViewMode = 'month' | 'week' | 'list'

const MODES: ViewMode[] = ['month', 'week', 'list']

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'

function SlotChip({ slot, onOpen }: { slot: Slot; onOpen: (slot: Slot) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(slot)}
      className="flex w-full items-baseline gap-1 rounded px-1 py-0.5 text-left text-xs hover:bg-wash"
      data-testid="calendar-slot"
      data-date={slot.date}
      data-name={slot.name}
      data-state={slot.state}
    >
      <span className="w-4 shrink-0 text-center text-muted">{kindGlyph(slot.kind)}</span>
      <span className="min-w-0 flex-1 truncate text-ink">{slot.name}</span>
      {slot.reactive && <span className="text-down">!</span>}
      <span className={stateTone(slot.state)}>{stateMark(slot.state)}</span>
    </button>
  )
}

function MonthGrid({ anchor, slots, onOpen }: { anchor: string; slots: Map<string, Slot[]>; onOpen: (slot: Slot) => void }) {
  const today = todayIso()
  return (
    <div data-testid="calendar-month">
      <div className="hidden grid-cols-7 border-b border-line text-xs text-muted sm:grid">
        {WEEKDAYS.map((name) => (
          <span key={name} className="px-2 py-1.5">
            {name}
          </span>
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-7">
        {monthGrid(anchor).map((day) => {
          const inMonth = sameMonth(day, anchor)
          return (
            <div
              key={day}
              className={cn(
                'min-h-[5.5rem] border-b border-line/60 p-1.5 sm:border-r',
                !inMonth && 'hidden bg-surface/60 text-muted sm:block',
                day === today && 'bg-wash/60',
              )}
              data-testid="calendar-day"
              data-date={day}
            >
              <span className={cn('block px-1 pb-1 text-xs', day === today ? 'font-semibold text-ink' : 'text-muted')}>{dayLabel(day)}</span>
              {(slots.get(day) ?? []).map((slot) => (
                <SlotChip key={slotKey(slot)} slot={slot} onOpen={onOpen} />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function WeekGrid({ anchor, slots, onOpen }: { anchor: string; slots: Slot[]; onOpen: (slot: Slot) => void }) {
  const days = weekDays(anchor)
  const times = [...new Set(slots.map(slotTime).filter((time): time is string => time !== null))].sort()
  const rows: (string | null)[] = slots.some((slot) => slotTime(slot) === null) ? [null, ...times] : times
  if (rows.length === 0) return <Empty testId="calendar-week-empty">no slots this week</Empty>
  return (
    <div className="overflow-x-auto" data-testid="calendar-week">
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="border-b border-line">
            <th className={cn(HEAD, 'w-20')}>hour</th>
            {days.map((day) => (
              <th key={day} className={HEAD} data-date={day}>
                {dayLabel(day)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((time) => (
            <tr key={time ?? 'all-day'} className="border-b border-line/30 last:border-0" data-testid="calendar-hour" data-hour={time ?? 'all day'}>
              <td className={cn(CELL, 'whitespace-nowrap tabular-nums text-muted')}>{time ?? 'all day'}</td>
              {days.map((day) => (
                <td key={day} className={cn(CELL, 'align-top')}>
                  {slots
                    .filter((slot) => slot.date === day && slotTime(slot) === time)
                    .map((slot) => (
                      <SlotChip key={slotKey(slot)} slot={slot} onOpen={onOpen} />
                    ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SlotList({ slots, onOpen }: { slots: Slot[]; onOpen: (slot: Slot) => void }) {
  if (slots.length === 0) return <Empty testId="calendar-list-empty">no slots in this range</Empty>
  return (
    <div className="overflow-x-auto" data-testid="calendar-list">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            <th className={HEAD}>day</th>
            <th className={HEAD}>slot</th>
            <th className={HEAD}>kind</th>
            <th className={HEAD}>look</th>
            <th className={HEAD}>state</th>
            <th className={HEAD}>proposal</th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot) => (
            <tr key={slotKey(slot)} className="border-b border-line/30 last:border-0" data-testid="calendar-list-row" data-state={slot.state}>
              <td className={cn(CELL, 'whitespace-nowrap text-muted')}>{dayLabel(slot.date)}</td>
              <td className={CELL}>
                <button type="button" className="font-medium text-ink hover:underline" onClick={() => onOpen(slot)} data-testid="calendar-list-open">
                  {slot.name}
                </button>
                {slot.reactive && <span className="ml-1 text-down">!</span>}
              </td>
              <td className={cn(CELL, 'whitespace-nowrap text-muted')}>
                {kindGlyph(slot.kind)} {slot.kind}
              </td>
              <td className={cn(CELL, 'text-muted')}>{slot.look ?? '—'}</td>
              <td className={cn(CELL, 'whitespace-nowrap')}>
                <span className={stateTone(slot.state)}>{stateMark(slot.state)}</span> <span className="text-muted">{slot.state}</span>
              </td>
              <td className={CELL}>
                {slot.proposal_seq === null ? (
                  <span className="text-muted">—</span>
                ) : (
                  <Link to={`/proposals/${slot.proposal_seq}`} className="text-ink underline" data-testid="calendar-list-proposal">
                    #{slot.proposal_seq}
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SlotDrawer({
  slot,
  onClose,
  onSkip,
  onRedo,
  skipping,
  redoing,
}: {
  slot: Slot | null
  onClose: () => void
  onSkip: (slot: Slot) => void
  onRedo: (seq: number, note: string) => void
  skipping: boolean
  redoing: boolean
}) {
  const [note, setNote] = useState('')
  const [asking, setAsking] = useState(false)
  const close = () => {
    setNote('')
    setAsking(false)
    onClose()
  }
  return (
    <Dialog open={slot !== null} onOpenChange={(open) => !open && close()}>
      <DialogContent data-testid="slot-drawer">
        {slot && (
          <>
            <div className="flex items-start justify-between gap-3">
              <DialogTitle>
                {dayLabel(slot.date)} · {slot.name}
              </DialogTitle>
              <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" onClick={close} data-testid="slot-drawer-close">
                <X size={16} />
              </Button>
            </div>

            <section data-testid="slot-spec">
              <h4 className="mb-2 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">calendar.yaml</h4>
              {slot.spec.length === 0 ? (
                <Empty testId="slot-spec-empty">no lines for this slot</Empty>
              ) : (
                <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-wash p-3 font-mono text-xs text-ink">
                  {slot.spec.join('\n')}
                </pre>
              )}
            </section>

            {slot.reactive && (
              <section data-testid="slot-reason">
                <h4 className="mb-2 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">reason</h4>
                <p className="text-sm text-ink">{slot.reason ?? 'reactive, no reason recorded'}</p>
              </section>
            )}

            <section data-testid="slot-proposal">
              <h4 className="mb-2 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">proposal</h4>
              {slot.proposal_seq === null ? (
                <p className="text-sm text-muted">none — the slot is {slot.state}</p>
              ) : (
                <p className="flex items-baseline gap-2 text-sm">
                  <Mono className="text-muted">#{slot.proposal_seq}</Mono>
                  <span className="text-ink">{slot.state}</span>
                  <Link to={`/proposals/${slot.proposal_seq}`} className="text-ink underline" onClick={close} data-testid="slot-proposal-link">
                    Open #{slot.proposal_seq}
                  </Link>
                </p>
              )}
            </section>

            {asking && slot.proposal_seq !== null && (
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="what to change"
                  className="h-8 flex-1 text-xs"
                  aria-label="redo note"
                  data-testid="slot-redo-note"
                />
                <Button
                  size="sm"
                  disabled={note.trim() === '' || redoing}
                  onClick={() => onRedo(slot.proposal_seq as number, note.trim())}
                  data-testid="slot-redo-submit"
                >
                  Send
                </Button>
              </div>
            )}

            <div className="mt-auto flex flex-wrap gap-2">
              <Button size="sm" disabled={skipping || slot.state === 'skipped'} onClick={() => onSkip(slot)} data-testid="slot-skip-btn">
                Skip
              </Button>
              <Button
                size="sm"
                disabled={slot.proposal_seq === null}
                title={slot.proposal_seq === null ? 'nothing drafted for this slot yet' : undefined}
                onClick={() => setAsking(true)}
                data-testid="slot-redo-btn"
              >
                Ask marketer to redo
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function Calendar() {
  const client = useQueryClient()
  const [mode, setMode] = useState<ViewMode>('month')
  const [anchor, setAnchor] = useState(todayIso())
  const [open, setOpen] = useState<Slot | null>(null)

  const days = mode === 'week' ? weekDays(anchor) : monthGrid(anchor)
  const from = days[0]
  const to = days[days.length - 1]
  const query = useQuery({ queryKey: ['calendar', from, to], queryFn: () => getCalendar(from, to) })
  const data = query.data

  const refresh = () => {
    client.invalidateQueries({ queryKey: ['calendar'] })
    client.invalidateQueries({ queryKey: ['today'] })
    client.invalidateQueries({ queryKey: ['proposals'] })
  }
  const fill = useMutation({ mutationFn: () => fillCalendar(14), onSuccess: refresh })
  const skip = useMutation({
    mutationFn: (slot: Slot) => skipSlot(slot.date, slot.name),
    onSuccess: () => {
      refresh()
      setOpen(null)
    },
  })
  const redo = useMutation({
    mutationFn: (input: { seq: number; note: string }) => redoProposal(input.seq, input.note),
    onSuccess: () => {
      refresh()
      setOpen(null)
    },
  })

  const step = (direction: number) => setAnchor(mode === 'week' ? addDays(anchor, direction * 7) : addMonths(anchor, direction))
  const slots = data?.slots ?? []
  const failed = fill.error ?? skip.error ?? redo.error ?? null

  return (
    <div className="space-y-4" data-testid="calendar-view" data-mode={mode} data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="calendar mode">
          {MODES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={mode === option}
              onClick={() => setMode(option)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                mode === option ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink',
              )}
              data-testid={`calendar-mode-${option}`}
            >
              {option}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted" aria-label="previous" onClick={() => step(-1)} data-testid="calendar-prev">
            <ChevronLeft size={16} />
          </Button>
          <span className="min-w-[10rem] text-center text-sm font-medium text-ink" data-testid="calendar-label">
            {mode === 'week' ? weekLabel(anchor) : monthLabel(anchor)}
          </span>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted" aria-label="next" onClick={() => step(1)} data-testid="calendar-next">
            <ChevronRight size={16} />
          </Button>
        </div>
        <Button size="sm" onClick={() => setAnchor(todayIso())} data-testid="calendar-today">
          Today
        </Button>
        <Button size="sm" disabled={fill.isPending} onClick={() => fill.mutate()} data-testid="calendar-fill">
          {fill.isPending ? 'Filling…' : 'Fill 14 days'}
        </Button>
      </div>

      {query.error && <ErrorBanner error={asApiError(query.error)} testId="calendar-error" />}
      {failed && <ErrorBanner error={asApiError(failed)} testId="calendar-action-error" />}
      {fill.data && <Banner testId="calendar-fill-started">marketer run #{fill.data.agent_run} started — it drafts every empty slot in the next 14 days</Banner>}
      {!data && !query.error && <Loading />}

      {data && (
        <Card className="p-0 sm:p-0">
          {slots.length === 0 && mode === 'month' ? (
            <Empty testId="calendar-empty">no slots in this month — calendar.yaml decides what belongs here</Empty>
          ) : mode === 'month' ? (
            <MonthGrid anchor={anchor} slots={byDate(slots)} onOpen={setOpen} />
          ) : mode === 'week' ? (
            <div className="p-3 sm:p-4">
              <WeekGrid anchor={anchor} slots={slots} onOpen={setOpen} />
            </div>
          ) : (
            <div className="p-3 sm:p-4">
              <SlotList slots={slots} onOpen={setOpen} />
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-2 text-xs text-muted">
            <span className="flex flex-wrap gap-3" data-testid="calendar-legend">
              {LEGEND.map((entry) => (
                <span key={entry.label}>
                  {entry.mark} {entry.label}
                </span>
              ))}
            </span>
            <span data-testid="calendar-cadence">{data.cadence.length === 0 ? 'no cadence set' : `${cadenceLine(data.cadence)} this month`}</span>
          </div>
        </Card>
      )}

      <SlotDrawer
        slot={open}
        onClose={() => setOpen(null)}
        onSkip={(slot) => skip.mutate(slot)}
        onRedo={(seq, note) => redo.mutate({ seq, note })}
        skipping={skip.isPending}
        redoing={redo.isPending}
      />
    </div>
  )
}
