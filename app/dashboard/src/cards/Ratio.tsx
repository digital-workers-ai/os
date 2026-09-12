import type { MetricResponse } from '@/api'
import { Figure } from '@/cards/Figure'
import { fixed } from '@/lib/format'

export function Ratio({ data }: { data: MetricResponse }) {
  return <Figure value={data.value} format={fixed} previous={data.previous} />
}
