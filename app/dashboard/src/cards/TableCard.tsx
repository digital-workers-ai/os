import type { UseQueryResult } from '@tanstack/react-query'
import { asApiError, type Column, type TableCardSpec, type TopResponse } from '@/api'
import { CardShell } from '@/cards/MetricCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'

export const tableId = (card: TableCardSpec) => `table-${card.entity}-${card.rank}`

const heading = (attr: string) => attr.replace(/_/g, ' ')

const text = (value: string | null, type: Column['type']) => {
  if (value === null || value === '') return '—'
  if (type === 'number') {
    const n = Number(value)
    return Number.isFinite(n) ? num(n) : value
  }
  if (type === 'date') return shortDate(value.slice(0, 10))
  return value
}

function Cell({ column, value, title }: { column: Column; value: string | null; title: boolean }) {
  const shown = text(value, column.type)
  if (column.type === 'number') {
    return (
      <td className={cn(CELL, 'whitespace-nowrap text-right tabular-nums text-ink')} data-attr={column.attr}>
        {shown}
      </td>
    )
  }
  if (column.type === 'date') {
    return (
      <td className={cn(CELL, 'whitespace-nowrap text-muted')} data-attr={column.attr}>
        {shown}
      </td>
    )
  }
  return (
    <td className={cn(CELL, title ? 'w-full max-w-0 font-medium text-ink' : 'max-w-48 text-muted')} data-attr={column.attr}>
      <span className="block truncate" title={value ?? undefined}>
        {shown}
      </span>
    </td>
  )
}

function Body({ card, query }: { card: TableCardSpec; query: UseQueryResult<TopResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const rows = query.data.rows
  if (rows.length === 0) return <Empty>no records</Empty>
  const title = card.columns.find((column) => column.type === 'string')?.attr
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="top-table">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            {card.columns.map((column) => (
              <th key={column.attr} className={cn(HEAD, column.type === 'number' && 'text-right')} data-attr={column.attr}>
                {heading(column.attr)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.canonical_id} className="border-b border-line/30 last:border-0" data-testid="top-row">
              {card.columns.map((column) => (
                <Cell key={column.attr} column={column} value={row.values[column.attr] ?? null} title={column.attr === title} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TableCard({ card, query, onDefinition }: { card: TableCardSpec; query: UseQueryResult<TopResponse>; onDefinition: () => void }) {
  return (
    <CardShell id={tableId(card)} shape="table" label={card.label} wide query={query} onDefinition={onDefinition}>
      <Body card={card} query={query} />
    </CardShell>
  )
}
