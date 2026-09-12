import { useState } from 'react'
import type { MetricResponse } from '@/api'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { num } from '@/lib/format'

const MAX_BARS = 8

type Bucket = [string, number | null]

const byValueDesc = (a: Bucket, b: Bucket) => (b[1] ?? -Infinity) - (a[1] ?? -Infinity) || a[0].localeCompare(b[0])

const cell = (value: number | null) => (value === null ? '—' : num(value))

export function Breakdown({ data }: { data: MetricResponse }) {
  const [more, setMore] = useState(false)
  const rows = Object.entries(data.breakdown ?? {}).sort(byValueDesc)
  if (rows.length === 0) return <Empty>no data</Empty>
  const top = Math.max(0, ...rows.map(([, value]) => value ?? 0))
  const bars = rows.slice(0, MAX_BARS)
  const rest = rows.slice(MAX_BARS)
  return (
    <div>
      <ul className="flex flex-col gap-2" data-testid="bars">
        {bars.map(([bucket, value]) => (
          <li key={bucket} data-testid="bar">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-ink">{bucket}</span>
              <span className="shrink-0 tabular-nums text-ink">{cell(value)}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-wash">
              <div className="h-full rounded-full bg-ink" style={{ width: `${top > 0 && value ? Math.max(0, (value / top) * 100) : 0}%` }} />
            </div>
          </li>
        ))}
      </ul>
      {rest.length > 0 && (
        <Button
          variant="link"
          size="sm"
          className="mt-2 h-auto px-0 text-muted"
          aria-expanded={more}
          onClick={() => setMore(!more)}
          data-testid="breakdown-more"
        >
          {more ? 'Hide' : `${num(rest.length)} more`}
        </Button>
      )}
      {more && (
        <table className="mt-1 w-full text-sm" data-testid="breakdown-table">
          <tbody>
            {rest.map(([bucket, value]) => (
              <tr key={bucket} className="border-t border-line/50">
                <td className="break-words py-1 pr-4 text-ink">{bucket}</td>
                <td className="py-1 text-right tabular-nums text-ink">{cell(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
