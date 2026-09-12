import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { asApiError, getFindings, type Finding, type Severity } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pager } from '@/components/ui/pager'
import { Pill } from '@/components/ui/pill'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const SIZE = 10
const SEVERITIES: Severity[] = ['high', 'medium', 'low']
const TONES: Record<Severity | 'all', string> = {
  high: 'bg-err/10 text-err',
  medium: 'bg-down/10 text-down',
  low: 'bg-wash text-ink',
  all: 'bg-wash text-ink',
}
const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted'
const CELL = 'py-2 pr-4 align-middle text-muted'

const bySeverity = (a: Finding, b: Finding) =>
  SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity) || a.rule.localeCompare(b.rule) || a.anchor.localeCompare(b.anchor)

function Option({ severity, count, on, onClick }: { severity: Severity | 'all'; count: number; on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',
        TONES[severity],
        on ? 'border-current' : 'border-transparent hover:border-line',
      )}
      data-testid="findings-filter-option"
      data-severity={severity}
    >
      {severity}
      <span className="tabular-nums opacity-70">{num(count)}</span>
    </button>
  )
}

export function Findings() {
  const query = useQuery({ queryKey: ['findings'], queryFn: getFindings })
  const data = query.data
  const [filter, setFilter] = useState<Severity | null>(null)
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(SIZE)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  const pick = (severity: Severity | 'all') => {
    setFilter(severity === 'all' || severity === filter ? null : severity)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(SIZE)
  }, [data])
  const all = data ? [...data.findings].sort(bySeverity) : []
  const findings = filter ? all.filter((f) => f.severity === filter) : all
  const page = findings.slice(offset, offset + size)

  return (
    <section className="mt-8 first:mt-0" data-testid="findings">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex items-baseline gap-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted">Needs attention</h2>
          {data && (
            <span className="text-xs text-muted" data-testid="findings-as-of">
              as of {shortDate(data.as_of.slice(0, 10))}
            </span>
          )}
        </div>
        {data && (
          <div className="flex flex-wrap gap-1.5" data-testid="findings-filter">
            <Option severity="all" count={all.length} on={filter === null} onClick={() => pick('all')} />
            {SEVERITIES.map((s) => (
              <Option key={s} severity={s} count={data.by_severity[s]} on={filter === s} onClick={() => pick(s)} />
            ))}
          </div>
        )}
      </div>
      <Card>
        {query.error && <ErrorBanner error={asApiError(query.error)} />}
        {!data && !query.error && <Loading />}
        {data && all.length === 0 && <Empty testId="findings-empty">no findings</Empty>}
        {all.length > 0 && findings.length === 0 && <Empty>no {filter} findings</Empty>}
        {findings.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="findings-table">
                <thead className="text-left text-muted">
                  <tr className="border-b border-line">
                    <th className={cn(HEAD, 'w-24')}>Severity</th>
                    <th className={HEAD}>Rule</th>
                    <th className={HEAD}>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {page.map((f) => (
                    <tr key={`${f.rule}|${f.anchor}`} className="border-b border-line/30 last:border-0" data-severity={f.severity}>
                      <td className={cn(CELL, 'whitespace-nowrap')}>
                        <Pill className={TONES[f.severity]}>{f.severity}</Pill>
                      </td>
                      <td className={CELL}>
                        <span className="block font-medium text-ink">{f.label}</span>
                        <Mono className="block">{f.rule}</Mono>
                      </td>
                      <td className={CELL}>
                        <span className="flex flex-wrap gap-1">
                          {Object.entries(f.evidence).map(([key, value]) => (
                            <span key={key} className="inline-block rounded-full border border-line px-2 py-0.5 font-mono text-[11px] text-muted">
                              {key} <strong className="font-medium text-ink">{value}</strong>
                            </span>
                          ))}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              offset={offset}
              count={page.length}
              total={findings.length}
              onPage={setOffset}
              size={size}
              allSize={findings.length}
              onSize={changeSize}
              pageSize={SIZE}
            />
          </>
        )}
      </Card>
    </section>
  )
}
