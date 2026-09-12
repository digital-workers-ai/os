import type { Previous } from '@/api'
import { Pill, type Tone } from '@/components/ui/pill'
import { delta, pct } from '@/lib/format'
import { previousLabel } from '@/lib/range'

function Delta({ value, previous }: { value: number | null; previous: Previous }) {
  const d = delta(value, previous.value)
  const tone: Tone = d === null || d === 0 ? 'neutral' : d > 0 ? 'ok' : 'down'
  const arrow = d === null || d === 0 ? '—' : d > 0 ? '▲' : '▼'
  return (
    <Pill tone={tone} title={previousLabel(previous.window_from, previous.window_to)} className="self-start" data-testid="delta">
      {arrow} {d === null ? '' : `${pct(d)} `}vs previous
    </Pill>
  )
}

export function Figure({ value, format, previous }: { value: number | null; format: (n: number) => string; previous?: Previous }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="truncate text-3xl font-medium tabular-nums text-ink" data-testid="value">
        {value === null ? <Pill tone="unknown">unknown</Pill> : format(value)}
      </div>
      {previous && <Delta value={value} previous={previous} />}
    </div>
  )
}
