import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { MetricResponse } from '@/api'
import { Empty } from '@/components/ui/empty'
import { compact, num, shortDate } from '@/lib/format'

const INK = '#1A1A1A'
const MUTED = '#807F74'
const LINE = '#E0DCC1'

export function Series({ data }: { data: MetricResponse }) {
  const points = Object.entries(data.breakdown ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([bucket, value]) => ({ bucket, value }))
  if (points.length === 0) return <Empty>no data</Empty>
  return (
    <div className="h-56 w-full" data-testid="series-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bucket" tickFormatter={shortDate} tick={{ fontSize: 11, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} minTickGap={24} />
          <YAxis tickFormatter={compact} tick={{ fontSize: 11, fill: MUTED }} axisLine={false} tickLine={false} width={44} />
          <Tooltip
            labelFormatter={(label) => shortDate(String(label))}
            formatter={(value) => [num(Number(value)), data.label]}
            contentStyle={{ fontSize: 12, borderColor: LINE, borderRadius: 8 }}
          />
          <Line type="monotone" dataKey="value" stroke={INK} strokeWidth={2} dot={{ r: 2, strokeWidth: 0, fill: INK }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
