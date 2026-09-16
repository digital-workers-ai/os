import type { VisibilityResponse } from '@/api'
import { ENGINES } from '@/lib/engines'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted'
const CELL = 'py-2 pr-4 align-middle'

const share = (rate: number | undefined) => (rate === undefined ? '—' : `${Math.round(rate * 100)}%`)

export function ShareTable({ data }: { data: VisibilityResponse }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>company</th>
            {ENGINES.map((engine) => (
              <th key={engine.value} className={cn(HEAD, 'text-right')}>
                {engine.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.companies.map((company) => (
            <tr
              key={company.name}
              className={cn('border-b border-line/30 last:border-0', company.role === 'brand' ? 'font-medium text-ink' : 'text-muted')}
              data-role={company.role}
            >
              <td className={cn(CELL, 'whitespace-nowrap')}>
                {company.name}
                {company.role === 'brand' && ' (you)'}
              </td>
              {ENGINES.map((engine) => (
                <td key={engine.value} className={cn(CELL, 'text-right tabular-nums')}>
                  {share(data.share[company.name]?.[engine.value])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
