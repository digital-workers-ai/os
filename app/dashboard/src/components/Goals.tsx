import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { asApiError, getGoals, type Goal } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Pill } from '@/components/ui/pill'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

const ERR = 'bg-err/10 text-err'
const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted'
const CELL = 'py-2 pr-4 align-middle text-muted'

function Verdict({ met }: { met: boolean | null }) {
  if (met === null) return <Pill tone="unknown">unknown</Pill>
  return met ? <Pill tone="ok">met</Pill> : <Pill className={ERR}>missed</Pill>
}

function Progress({ value }: { value?: number | null }) {
  if (typeof value !== 'number') return <>—</>
  return (
    <span className="inline-flex items-center gap-2">
      <span className="block h-1.5 w-24 rounded-full bg-wash">
        <span className="block h-full rounded-full bg-ink" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </span>
      <span className="text-xs tabular-nums">{num(value)}%</span>
    </span>
  )
}

function GoalsTable({ goals }: { goals: Goal[] }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [goals])
  const page = goals.slice(offset, offset + size)
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="goals-table">
          <thead className="text-left text-muted">
            <tr className="border-b border-line">
              <th className={HEAD}>Goal</th>
              <th className={cn(HEAD, 'text-right')}>Target</th>
              <th className={cn(HEAD, 'text-right')}>Current</th>
              <th className={HEAD}>Verdict</th>
              <th className={HEAD}>Progress</th>
            </tr>
          </thead>
          <tbody>
            {page.map((g) => (
              <tr key={g.goal} className="border-b border-line/30 last:border-0">
                <td className={CELL}>
                  <span className="block font-medium text-ink">{g.label}</span>
                  <Mono className="block">{g.metric}</Mono>
                </td>
                <td className={cn(CELL, 'text-right tabular-nums')}>{g.target === undefined ? '—' : num(g.target)}</td>
                <td className={cn(CELL, 'text-right tabular-nums')}>
                  {g.current === null ? <Pill tone="unknown">unknown</Pill> : num(g.current)}
                </td>
                <td className={CELL}>
                  <Verdict met={g.met} />
                </td>
                <td className={CELL}>
                  <Progress value={g.progress} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} count={page.length} total={goals.length} onPage={setOffset} size={size} allSize={goals.length} onSize={changeSize} />
    </>
  )
}

export function Goals() {
  const query = useQuery({ queryKey: ['goals'], queryFn: getGoals })
  const data = query.data
  return (
    <section className="mt-8 first:mt-0" data-testid="goals">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted">Goals</h2>
        {data && (
          <div className="flex flex-wrap gap-1.5" data-testid="goals-pills">
            <Pill tone="ok">{num(data.met)} met</Pill>
            <Pill className={ERR}>{num(data.missed)} missed</Pill>
            <Pill>{num(data.unknown)} unknown</Pill>
          </div>
        )}
      </div>
      <Card>
        {query.error && <ErrorBanner error={asApiError(query.error)} />}
        {!data && !query.error && <Loading />}
        {data && data.goals.length === 0 && <Empty testId="goals-empty">no goals</Empty>}
        {data && data.goals.length > 0 && <GoalsTable goals={data.goals} />}
      </Card>
    </section>
  )
}
