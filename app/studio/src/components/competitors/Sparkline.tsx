import { cn } from '@/lib/utils'

const PAD = 2
const STROKE = '#1A1A1A'

type Point = { index: number; value: number }

function segments(points: (number | null)[]): Point[][] {
  const runs: Point[][] = []
  let run: Point[] = []
  points.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) {
      if (run.length > 0) runs.push(run)
      run = []
      return
    }
    run.push({ index, value })
  })
  if (run.length > 0) runs.push(run)
  return runs
}

export function Sparkline({
  points,
  width = 80,
  height = 20,
  invert = false,
  testId,
  className,
}: {
  points: (number | null)[]
  width?: number
  height?: number
  invert?: boolean
  testId?: string
  className?: string
}) {
  const runs = segments(points)
  const values = runs.flat().map((point) => point.value)
  if (values.length === 0)
    return (
      <span className={cn('text-muted', className)} data-testid={testId}>
        —
      </span>
    )
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || 1
  const step = points.length > 1 ? (width - PAD * 2) / (points.length - 1) : 0
  const x = (index: number) => (points.length > 1 ? PAD + index * step : width / 2)
  const y = (value: number) => {
    const ratio = (value - low) / span
    return PAD + (invert ? ratio : 1 - ratio) * (height - PAD * 2)
  }
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn('inline-block align-middle', className)}
      aria-hidden="true"
      data-testid={testId}
    >
      {runs.map((run) =>
        run.length === 1 ? (
          <circle key={run[0].index} cx={x(run[0].index)} cy={y(run[0].value)} r={1.25} fill={STROKE} />
        ) : (
          <polyline
            key={run[0].index}
            points={run.map((point) => `${x(point.index)},${y(point.value)}`).join(' ')}
            fill="none"
            stroke={STROKE}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ),
      )}
    </svg>
  )
}
