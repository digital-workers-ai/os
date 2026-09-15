import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { asApiError, getSwipeItem, type SwipeItem } from '@/api'
import { Remix } from '@/components/competitors/Remix'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { num, shortDate } from '@/lib/format'

const HEADING = 'mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted'
const IMAGE_URL = /\.(png|jpe?g|gif|webp|avif)(\?|$)/i

function Creative({ item }: { item: SwipeItem }) {
  const asImage = item.format === 'image' && IMAGE_URL.test(item.url)
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-wash" data-testid="swipe-creative">
      {asImage ? (
        <img src={item.url} alt={`${item.competitor} ${item.format}`} className="mx-auto max-h-96 w-full object-contain" />
      ) : (
        <div className="flex min-h-40 flex-col items-center justify-center gap-1 p-6 text-center text-sm text-muted">
          <span>creative as it arrived</span>
          <span className="text-ink">
            {item.format} · {item.platform}
          </span>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="text-ink underline"
            data-testid="swipe-creative-link"
          >
            open ↗
          </a>
        </div>
      )}
    </div>
  )
}

function Copy({ item }: { item: SwipeItem }) {
  return (
    <div className="mt-3 space-y-1.5 text-sm" data-testid="swipe-copy">
      {item.headline && <p className="font-medium text-ink">{item.headline}</p>}
      {item.body && <p className="text-ink">{item.body}</p>}
      {item.landing_url && (
        <a
          href={item.landing_url}
          target="_blank"
          rel="noreferrer"
          className="block break-all text-ink underline"
          data-testid="swipe-landing"
        >
          {item.landing_url} ↗
        </a>
      )}
      <p className="text-muted">
        seen: {shortDate(item.first_seen)} → {item.last_seen ? shortDate(item.last_seen) : 'now'}
      </p>
      <p className="text-muted">
        <Mono>raw_event</Mono> ×{num(item.raw_events)}, one per sync
      </p>
    </div>
  )
}

function Labels({ item }: { item: SwipeItem }) {
  return (
    <div data-testid="swipe-labels">
      <h2 className={HEADING}>Labels</h2>
      {item.labels.length === 0 ? (
        <Empty testId="swipe-labels-empty">enrichment read no labels</Empty>
      ) : (
        <div className="divide-y divide-line/30">
          {item.labels.map((label) => (
            <div
              key={`${label.field}|${label.label}`}
              className="flex flex-wrap items-baseline gap-2 py-1.5"
              data-testid="swipe-label"
              data-field={label.field}
            >
              <Mono className="w-14 shrink-0 text-muted">{label.field}</Mono>
              <Pill>{label.label}</Pill>
              {label.quote && <span className="min-w-0 flex-1 text-sm italic text-muted">“{label.quote}”</span>}
            </div>
          ))}
        </div>
      )}
      {item.counter !== null && (
        <p className="mt-3 border-t border-line/50 pt-2 text-sm text-ink" data-testid="swipe-counter">
          our counter: {item.counter}
        </p>
      )}
    </div>
  )
}

function Body({ error, data }: { error: unknown; data?: SwipeItem }) {
  if (error) return <ErrorBanner error={asApiError(error)} testId="swipe-item-error" />
  if (!data) return <Loading />
  return (
    <>
      <p className="flex flex-wrap items-baseline gap-x-2 text-sm text-muted" data-testid="swipe-item-line">
        <Mono className="text-ink">{data.id}</Mono>
        <span>·</span>
        <span className="font-medium text-ink">{data.competitor}</span>
        <span>·</span>
        <span>{data.platform}</span>
        <span>·</span>
        <span>
          {data.running ? 'running' : 'ran'} {num(data.days_running)} days (since {shortDate(data.first_seen)})
        </span>
      </p>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-4 sm:p-5">
          <h2 className={HEADING}>Creative</h2>
          <Creative item={data} />
          <Copy item={data} />
        </Card>
        <Card className="p-4 sm:p-5">
          <Labels item={data} />
        </Card>
      </div>
      <Remix item={data} />
    </>
  )
}

export function SwipeItemView() {
  const { id = '' } = useParams()
  const query = useQuery({ queryKey: ['swipe-item', id], queryFn: () => getSwipeItem(id) })
  return (
    <div className="space-y-4" data-testid="swipe-item-view" data-id={id}>
      <Link to="/competitors/swipe" className="inline-block text-sm text-muted hover:text-ink" data-testid="swipe-back">
        ◂ Swipe file
      </Link>
      <Body error={query.error} data={query.data} />
    </div>
  )
}
