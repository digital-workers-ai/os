import { ExternalLink } from 'lucide-react'
import type { Ad, Post } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Pill } from '@/components/ui/pill'
import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

export const NEWEST = 5

interface Item {
  key: string
  company: string
  kind: string
  name: string | null
  date: string
  url: string
}

const newest = <T,>(rows: T[], date: (row: T) => string) => [...rows].sort((a, b) => date(b).localeCompare(date(a))).slice(0, NEWEST)

const fromAd = (ad: Ad): Item => ({ key: `ad|${ad.canonical_id}`, company: ad.company, kind: 'Google ad', name: ad.name, date: ad.last_seen, url: ad.url })

const fromPost = (post: Post): Item => ({
  key: `post|${post.canonical_id}`,
  company: post.company,
  kind: 'LinkedIn post',
  name: post.name,
  date: post.posted_at,
  url: post.url,
})

const activity = (ads: Ad[], posts: Post[]): Item[] =>
  [...newest(ads, (ad) => ad.last_seen).map(fromAd), ...newest(posts, (post) => post.posted_at).map(fromPost)].sort(
    (a, b) => b.date.localeCompare(a.date) || a.key.localeCompare(b.key),
  )

export function ActivityList({ ads, posts }: { ads: Ad[]; posts: Post[] }) {
  const items = activity(ads, posts)
  if (items.length === 0) return <Empty>no activity yet</Empty>
  return (
    <ul className="divide-y divide-line/30 text-sm">
      {items.map((item) => (
        <li key={item.key} className="flex items-center gap-3 py-2" data-kind={item.kind}>
          <span className="w-24 shrink-0 truncate font-medium text-ink" title={item.company}>
            {item.company}
          </span>
          <Pill className="shrink-0">{item.kind}</Pill>
          <span className={cn('min-w-0 flex-1 truncate', item.name ? 'text-ink' : 'italic text-muted')} title={item.name ?? undefined}>
            {item.name ?? 'text not read yet'}
          </span>
          <span className="shrink-0 whitespace-nowrap text-xs text-muted">{shortDate(item.date.slice(0, 10))}</span>
          {item.url && (
            <a href={item.url} target="_blank" rel="noreferrer" className="shrink-0 text-muted hover:text-ink" aria-label="open">
              <ExternalLink size={14} />
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}
