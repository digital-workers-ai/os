import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { asApiError, getCalendar, getLooks, remixSwipeItem, type Kind, type SwipeItem } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Mono } from '@/components/ui/mono'
import { shortDate } from '@/lib/format'

const KINDS: Kind[] = ['post', 'newsletter', 'blog', 'image', 'video', 'ad']

const KEEPS: [string, string][] = [
  ['hook', 'hook type'],
  ['structure', 'structure'],
  ['offer', 'offer'],
]

const SELECT = 'h-8 rounded-md border border-line bg-paper px-2 text-xs text-ink'
const FIELD = 'flex items-center gap-1.5 text-xs text-muted'
const SLOT_WINDOW_DAYS = 14
const DAY_MS = 24 * 60 * 60 * 1000

const isoDay = (at: number) => new Date(at).toISOString().slice(0, 10)

export function Remix({ item }: { item: SwipeItem }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<Kind>('ad')
  const [look, setLook] = useState('')
  const [slot, setSlot] = useState('')
  const [keep, setKeep] = useState<Record<string, boolean>>({ hook: true, structure: true, offer: false })

  const from = isoDay(Date.now())
  const to = isoDay(Date.now() + SLOT_WINDOW_DAYS * DAY_MS)
  const looks = useQuery({ queryKey: ['looks'], queryFn: getLooks })
  const calendar = useQuery({ queryKey: ['calendar', from, to], queryFn: () => getCalendar(from, to) })
  const remix = useMutation({
    mutationFn: () =>
      remixSwipeItem(item.id, {
        kind,
        look: look || null,
        slot: slot || null,
        keep: KEEPS.filter(([name]) => keep[name]).map(([name]) => name),
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] })
      queryClient.invalidateQueries({ queryKey: ['today'] })
      navigate(`/proposals/${result.proposal}`)
    },
  })

  const openSlots = (calendar.data?.slots ?? []).filter((each) => each.state === 'empty')

  return (
    <Card className="space-y-3 p-4 sm:p-5" data-testid="remix-bar">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted">Remix</h2>
        <label className={FIELD}>
          kind
          <select
            className={SELECT}
            value={kind}
            onChange={(event) => setKind(event.target.value as Kind)}
            data-testid="remix-kind"
          >
            {KINDS.map((each) => (
              <option key={each} value={each}>
                {each}
              </option>
            ))}
          </select>
        </label>
        <label className={FIELD}>
          look
          <select
            className={SELECT}
            value={look}
            onChange={(event) => setLook(event.target.value)}
            data-testid="remix-look"
          >
            <option value="">no look</option>
            {(looks.data?.looks ?? []).map((each) => (
              <option key={each.name} value={each.name}>
                {each.name}
              </option>
            ))}
          </select>
        </label>
        <label className={FIELD}>
          slot
          <select
            className={SELECT}
            value={slot}
            onChange={(event) => setSlot(event.target.value)}
            data-testid="remix-slot"
          >
            <option value="">no slot (reactive)</option>
            {openSlots.map((each) => (
              <option key={`${each.date}|${each.name}`} value={each.date}>
                {shortDate(each.date)} {each.name}
              </option>
            ))}
          </select>
        </label>
        <Mono className="text-muted">skill: dw-remix</Mono>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="text-xs text-muted">keep:</span>
        {KEEPS.map(([name, label]) => (
          <label key={name} className="flex items-center gap-1.5 text-sm text-ink">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 accent-ink"
              checked={keep[name]}
              onChange={(event) => setKeep({ ...keep, [name]: event.target.checked })}
              data-testid={`remix-keep-${name}`}
            />
            {label}
          </label>
        ))}
        <Button
          size="sm"
          className="sm:ml-auto"
          disabled={remix.isPending}
          onClick={() => remix.mutate()}
          data-testid="remix-btn"
        >
          Remix → draft proposal
        </Button>
      </div>

      {remix.error && <ErrorBanner error={asApiError(remix.error)} testId="remix-error" />}

      <p className="text-xs text-muted">
        Remix runs <Mono>dw-remix</Mono> on the backend in draft mode.
      </p>
    </Card>
  )
}
