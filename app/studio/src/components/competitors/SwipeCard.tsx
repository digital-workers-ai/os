import { Link } from 'react-router-dom'
import type { SwipeRow } from '@/api'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Pill } from '@/components/ui/pill'

const OPENING = 90

const glyph = (format: string) => {
  if (format === 'video') return '▶'
  if (format === 'image') return '▣'
  return format.includes('post') ? 'in' : '▣'
}

const opening = (item: SwipeRow) => {
  if (item.headline) return item.headline
  return item.body.length > OPENING ? `${item.body.slice(0, OPENING).trimEnd()}…` : item.body
}

export function SwipeCard({ item }: { item: SwipeRow }) {
  const labels: [string, string | null][] = [
    ['angle', item.angle],
    ['hook', item.hook],
    ['format', item.format],
  ]
  return (
    <Card
      className="relative flex h-full flex-col gap-2 p-3 transition-colors hover:bg-wash sm:p-4"
      data-testid="swipe-card"
      data-id={item.id}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-muted">{glyph(item.format)}</span>
        <Link
          to={`/competitors/swipe/${item.id}`}
          className="min-w-0 flex-1 truncate font-medium text-ink after:absolute after:inset-0"
          data-testid="swipe-card-link"
        >
          {item.competitor}
        </Link>
        {!item.running && <Pill tone="unknown">stopped</Pill>}
      </div>
      <p className="text-xs text-muted">
        {item.days_running}d · {item.platform}
      </p>
      <div className="flex flex-wrap gap-1">
        {labels.map(([field, label]) =>
          label === null ? null : (
            <Pill key={field}>{label}</Pill>
          ),
        )}
      </div>
      <p className="max-h-[3.75rem] overflow-hidden text-sm text-ink">“{opening(item)}”</p>
      <Link
        to={`/competitors/swipe/${item.id}`}
        className={buttonVariants({ variant: 'outline', size: 'sm', className: 'relative mt-auto w-full' })}
        data-testid="remix-btn"
      >
        Remix
      </Link>
    </Card>
  )
}
