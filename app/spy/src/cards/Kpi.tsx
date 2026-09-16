import type { MetricResponse } from '@/api'
import { Figure } from '@/cards/Figure'
import { num } from '@/lib/format'

export function Kpi({ data }: { data: MetricResponse }) {
  return <Figure value={data.value} format={num} previous={data.previous} />
}
