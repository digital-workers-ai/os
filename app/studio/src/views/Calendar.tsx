import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { asApiError, fillCalendar, getCalendar, runSlot, skipSlot, type Cadence, type Slot } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Hint } from '@/components/ui/hint'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import {
  calendarRange,
  kindGlyph,
  MARK_LABELS,
  MODE_LABELS,
  MODES,
  monthGrid,
  rangeLabel,
  slotsByDate,
  sortSlots,
  stateMark,
  step,
  todayIso,
  WEEKDAYS,
  weekday,
  weekDays,
  type Mode,
} from '@/lib/calendar'
import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const link = 'text-ink underline underline-offset-2'

const FILL_HINT =
  'Runs the marketer AI agent now rather than waiting for its daily run: it fills every slot in the next fourteen days that is still empty and not skipped, one paid model run each.'

const RUN_HINT = 'Runs the skill this slot names on its theme, now, as one paid model run; the asset opens while it is still building.'

const SKIP_HINT = 'Records that this slot is not to be made, so both the daily fill and Fill next 14 days pass over it.'

const CADENCE_HINT = 'For the range in view, how many slots of each kind are built out of those planned; a skipped slot counts in neither.'

const option = (active: boolean) =>
  cn('rounded-md px-2.5 py-1 text-xs font-medium transition-colors', active ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink')

const useInvalidate = () => {
  const client = useQueryClient()
  return () => client.invalidateQueries({ queryKey: ['calendar'] })
}

function Chip({ slot, time, onPick }: { slot: Slot; time?: boolean; onPick: (slot: Slot) => void }) {
  return (
    <button
      type="button"
      onClick={() => onPick(slot)}
      className={cn('flex w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-left text-xs text-ink hover:bg-wash', slot.state === 'skipped' && 'text-muted line-through')}
      data-testid="calendar-slot"
      data-date={slot.date}
      data-name={slot.name}
      data-state={slot.state}
    >
      {time && <span className="shrink-0 tabular-nums text-muted">{slot.time}</span>}
      <span className="shrink-0" title={slot.kind}>
        {kindGlyph(slot.kind)}
      </span>
      <span className="min-w-0 flex-1 truncate">{slot.name}</span>
      <span className="shrink-0" title={slot.state}>
        {stateMark(slot.state)}
      </span>
    </button>
  )
}

function Month({ anchor, today, byDate, onPick }: { anchor: string; today: string; byDate: Map<string, Slot[]>; onPick: (slot: Slot) => void }) {
  const month = anchor.slice(0, 7)
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-paper" data-testid="calendar-month">
      <div className="grid grid-cols-7 border-b border-line bg-wash text-center text-xs font-medium uppercase text-muted">
        {WEEKDAYS.map((day) => (
          <div key={day} className="py-1.5">
            {day}
          </div>
        ))}
      </div>
      {monthGrid(anchor).map((week) => (
        <div key={week[0]} className="grid grid-cols-7 border-b border-line last:border-b-0">
          {week.map((date) => (
            <div
              key={date}
              className={cn('min-h-[88px] border-r border-line p-1 last:border-r-0', !date.startsWith(month) && 'bg-surface')}
              data-testid="calendar-day"
              data-date={date}
            >
              <div className={cn('mb-1 px-1 text-xs tabular-nums', date === today ? 'font-semibold text-brand' : 'text-muted')}>{Number(date.slice(8))}</div>
              {(byDate.get(date) ?? []).map((slot) => (
                <Chip key={slot.name} slot={slot} onPick={onPick} />
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function Week({ anchor, today, byDate, onPick }: { anchor: string; today: string; byDate: Map<string, Slot[]>; onPick: (slot: Slot) => void }) {
  return (
    <div className="grid grid-cols-7 overflow-hidden rounded-xl border border-line bg-paper" data-testid="calendar-week">
      {weekDays(anchor).map((date) => (
        <div key={date} className="min-h-[200px] border-r border-line p-1.5 last:border-r-0" data-testid="calendar-day" data-date={date}>
          <div className={cn('mb-2 text-xs', date === today ? 'font-semibold text-brand' : 'text-muted')}>
            {weekday(date)} {shortDate(date)}
          </div>
          {(byDate.get(date) ?? []).map((slot) => (
            <Chip key={slot.name} slot={slot} time onPick={onPick} />
          ))}
        </div>
      ))}
    </div>
  )
}

function List({ slots, onPick }: { slots: Slot[]; onPick: (slot: Slot) => void }) {
  if (slots.length === 0) return <Empty testId="calendar-list-empty">no slots this month</Empty>
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-paper" data-testid="calendar-list">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase text-muted">
            {['Date', 'Time', 'Kind', 'Name', 'State', 'Asset'].map((head) => (
              <th key={head} className="px-3 py-2 font-medium">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortSlots(slots).map((slot) => (
            <tr
              key={`${slot.date}/${slot.name}`}
              className="cursor-pointer border-b border-line/50 last:border-b-0 hover:bg-wash"
              onClick={() => onPick(slot)}
              data-testid="calendar-slot"
              data-date={slot.date}
              data-name={slot.name}
              data-state={slot.state}
            >
              <td className="px-3 py-1.5 whitespace-nowrap">
                {weekday(slot.date)} {shortDate(slot.date)}
              </td>
              <td className="px-3 py-1.5 tabular-nums">{slot.time}</td>
              <td className="px-3 py-1.5">
                {kindGlyph(slot.kind)} {slot.kind}
              </td>
              <td className="px-3 py-1.5">{slot.name}</td>
              <td className="px-3 py-1.5">
                {stateMark(slot.state)} {slot.state}
              </td>
              <td className="px-3 py-1.5">
                {slot.asset_seq !== null && (
                  <Link to={`/assets/${slot.asset_seq}`} className={link} onClick={(e) => e.stopPropagation()} data-testid="calendar-slot-link">
                    #{slot.asset_seq}
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

function Row({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 text-sm">
      <dt className="w-16 shrink-0 text-muted">{name}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

function SlotBody({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const navigate = useNavigate()
  const invalidate = useInvalidate()
  const run = useMutation({
    mutationFn: () => runSlot(slot.date, slot.name),
    onSuccess: async (res) => {
      await invalidate()
      navigate(`/assets/${res.asset.seq}`)
    },
  })
  const skip = useMutation({
    mutationFn: () => skipSlot(slot.date, slot.name),
    onSuccess: async () => {
      await invalidate()
      onClose()
    },
  })
  const error = run.error ?? skip.error
  const busy = run.isPending || skip.isPending
  return (
    <DialogContent data-testid="slot-dialog" data-date={slot.date} data-name={slot.name} data-state={slot.state}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <DialogTitle className="truncate">{slot.name}</DialogTitle>
          <Pill className="mt-1" title={slot.state}>
            {stateMark(slot.state)} {slot.state}
          </Pill>
        </div>
        <DialogClose asChild>
          <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" data-testid="slot-close">
            <X size={16} />
          </Button>
        </DialogClose>
      </div>
      <dl className="flex flex-col gap-1.5" data-testid="slot-spec">
        <Row name="kind">
          {kindGlyph(slot.kind)} {slot.kind}
        </Row>
        <Row name="skill">
          <Mono>{slot.skill}</Mono>
        </Row>
        <Row name="when">
          {weekday(slot.date)} {shortDate(slot.date)} · {slot.time}
        </Row>
        <Row name="look">{slot.look ?? '—'}</Row>
        <Row name="ratio">{slot.ratio ?? '—'}</Row>
        <Row name="theme">{slot.theme}</Row>
      </dl>
      {slot.asset_seq !== null && (
        <Link to={`/assets/${slot.asset_seq}`} className={cn('text-sm', link)} data-testid="slot-asset">
          Open asset #{slot.asset_seq}
        </Link>
      )}
      {error && <ErrorBanner error={asApiError(error)} testId="slot-error" />}
      <div className="flex items-center gap-2">
        <Button onClick={() => run.mutate()} disabled={busy || slot.state === 'built'} data-testid="slot-run">
          {run.isPending ? 'running…' : 'Run now'}
        </Button>
        <Hint text={RUN_HINT} />
        <Button variant="ghost" onClick={() => skip.mutate()} disabled={busy || slot.state !== 'empty'} data-testid="slot-skip">
          Skip
        </Button>
        <Hint text={SKIP_HINT} />
      </div>
    </DialogContent>
  )
}

function Footer({ cadence }: { cadence: Cadence[] }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted" data-testid="calendar-footer">
      <span data-testid="calendar-legend">
        {MARK_LABELS.map(([state, label]) => (
          <span key={state} className="mr-3">
            {stateMark(state)} {label}
          </span>
        ))}
      </span>
      <span data-testid="calendar-cadence">
        {cadence.map((c) => `${c.done}/${c.planned} ${c.kind}`).join(' · ')}
        <Hint text={CADENCE_HINT} />
      </span>
    </div>
  )
}

export function Calendar() {
  const [today] = useState(todayIso)
  const [mode, setMode] = useState<Mode>('month')
  const [anchor, setAnchor] = useState(today)
  const [open, setOpen] = useState<Slot | null>(null)
  const { from, to } = calendarRange(mode, anchor)
  const query = useQuery({ queryKey: ['calendar', from, to], queryFn: () => getCalendar(from, to) })
  const invalidate = useInvalidate()
  const fill = useMutation({ mutationFn: () => fillCalendar(14), onSuccess: invalidate })
  const byDate = slotsByDate(query.data?.slots ?? [])
  const state = query.isPending ? 'loading' : query.isError ? 'error' : 'ready'
  return (
    <div className="flex flex-col gap-4" data-testid="calendar-view" data-state={state}>
      <div className="flex flex-wrap items-center gap-2" data-testid="calendar-toolbar">
        <div className="flex items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="mode">
          {MODES.map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)} className={option(mode === m)} data-testid={`calendar-mode-${m}`}>
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setAnchor(step(mode, anchor, -1))} aria-label="previous" data-testid="calendar-prev">
            <ChevronLeft size={16} />
          </Button>
          <span className="min-w-[10rem] text-center text-sm font-medium text-ink" data-testid="calendar-label">
            {rangeLabel(mode, anchor)}
          </span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setAnchor(step(mode, anchor, 1))} aria-label="next" data-testid="calendar-next">
            <ChevronRight size={16} />
          </Button>
          <Button variant="ghost" size="sm" className="h-8" onClick={() => setAnchor(today)} data-testid="calendar-today">
            Today
          </Button>
        </div>
        <Button size="sm" className="ml-auto h-8" onClick={() => fill.mutate()} disabled={fill.isPending} data-testid="calendar-fill">
          {fill.isPending ? 'filling…' : 'Fill next 14 days'}
        </Button>
        <Hint text={FILL_HINT} />
      </div>
      {fill.error && <ErrorBanner error={asApiError(fill.error)} testId="calendar-fill-error" />}
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBanner error={asApiError(query.error)} />
      ) : (
        <>
          {mode === 'month' && <Month anchor={anchor} today={today} byDate={byDate} onPick={setOpen} />}
          {mode === 'week' && <Week anchor={anchor} today={today} byDate={byDate} onPick={setOpen} />}
          {mode === 'list' && <List slots={query.data.slots} onPick={setOpen} />}
          <Footer cadence={query.data.cadence} />
        </>
      )}
      <Dialog open={!!open} onOpenChange={(isOpen) => !isOpen && setOpen(null)}>
        {open && <SlotBody key={`${open.date}/${open.name}`} slot={open} onClose={() => setOpen(null)} />}
      </Dialog>
    </div>
  )
}
