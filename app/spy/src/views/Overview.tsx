import { useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { getAds, getMetric, getPosts, getVisibility, type MetricCardSpec, type MetricResponse } from '@/api'
import { MetricCard } from '@/cards/MetricCard'
import { Series } from '@/cards/Series'
import { ActivityList, NEWEST } from '@/components/ActivityList'
import { EmptyPage } from '@/components/EmptyPage'
import { MetricInfo } from '@/components/MetricInfo'
import { ShareTable } from '@/components/ShareTable'
import { StateSection } from '@/components/StateSection'
import { Card } from '@/components/ui/card'
import { Pending, spanOf, type RangedProps } from '@/views/ranged'

const CARDS: MetricCardSpec[] = [
  { metric: 'brand_mention_rate', label: 'Brand mention rate', shape: 'ratio' },
  { metric: 'ai_overview_brand_mentions', label: 'AI Overview mentions', shape: 'kpi' },
  { metric: 'brand_google_position', label: 'Google position', shape: 'ratio' },
  { metric: 'competitor_ads', label: 'Competitor ads', shape: 'kpi' },
]

const rateByDay = (mentions: MetricResponse, checks: MetricResponse): MetricResponse => ({
  ...checks,
  label: 'Brand mention rate %',
  breakdown: Object.fromEntries(
    Object.entries(checks.breakdown ?? {}).map(([day, n]) => [day, n ? Math.round((100 * (mentions.breakdown?.[day] ?? 0)) / n) : 0]),
  ),
})

export function Overview(props: RangedProps) {
  const span = spanOf(props)
  const enabled = !!span
  const [open, setOpen] = useState<MetricCardSpec | null>(null)
  const cards = useQueries({
    queries: CARDS.map((card) => ({
      queryKey: ['metric', card.metric, span, 'previous'],
      queryFn: () => getMetric(card.metric, { ...span, compare: 'previous' as const }),
      enabled,
    })),
  })
  const mentions = useQuery({
    queryKey: ['metric', 'brand_mentions_by_day', span],
    queryFn: () => getMetric('brand_mentions_by_day', { ...span }),
    enabled,
  })
  const checks = useQuery({ queryKey: ['metric', 'checks_by_day', span], queryFn: () => getMetric('checks_by_day', { ...span }), enabled })
  const visibility = useQuery({ queryKey: ['visibility', 'all', span], queryFn: () => getVisibility(undefined, span ?? undefined), enabled })
  const ads = useQuery({ queryKey: ['ads', 'all', span], queryFn: () => getAds(undefined, span ?? undefined), enabled })
  const posts = useQuery({ queryKey: ['posts', { limit: NEWEST }, span], queryFn: () => getPosts({ limit: NEWEST }, span ?? undefined), enabled })
  if (!span) return <Pending error={props.todayError} />
  if (visibility.data?.checks === 0 && ads.data?.ads.length === 0 && posts.data?.posts.length === 0) return <EmptyPage />
  const opened = open ? { card: open, last: cards[CARDS.indexOf(open)]?.data } : null
  return (
    <>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="overview-cards">
        {CARDS.map((card, i) => (
          <MetricCard key={card.metric} card={card} query={cards[i]} onDefinition={() => setOpen(card)} />
        ))}
      </div>
      <StateSection id="share-table" label="Share of voice by engine" queries={[visibility]} className="mt-8">
        <Card>{visibility.data && <ShareTable data={visibility.data} />}</Card>
      </StateSection>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <StateSection id="mention-series" label="Brand mentions by day" queries={[mentions, checks]}>
          <Card>{mentions.data && checks.data && <Series data={rateByDay(mentions.data, checks.data)} />}</Card>
        </StateSection>
        <StateSection id="activity-list" label="Latest competitor activity" queries={[ads, posts]}>
          <Card>{ads.data && posts.data && <ActivityList ads={ads.data.ads} posts={posts.data.posts} />}</Card>
        </StateSection>
      </div>
      <MetricInfo open={opened} onClose={() => setOpen(null)} />
    </>
  )
}
