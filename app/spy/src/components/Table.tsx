import type { ReactNode } from 'react'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="spy-table">
        {children}
      </table>
    </div>
  )
}

export function Head({ children }: { children: ReactNode }) {
  return (
    <thead className="text-left text-muted">
      <tr className="border-b border-line">{children}</tr>
    </thead>
  )
}

export function Row({ children }: { children: ReactNode }) {
  return <tr className="border-b border-line/30 last:border-0">{children}</tr>
}

export function Th({ right = false, strong = false, children }: { right?: boolean; strong?: boolean; children: ReactNode }) {
  return (
    <th scope="col" className={cn(HEAD, right && 'text-right', strong && 'font-semibold text-ink')}>
      {children}
    </th>
  )
}

export function Cell({ className, children }: { className?: string; children: ReactNode }) {
  return <td className={cn(CELL, className)}>{children}</td>
}

export function NumCell({ value }: { value: number | null }) {
  return <Cell className="whitespace-nowrap text-right tabular-nums text-ink">{value === null ? '—' : num(value)}</Cell>
}

export function DateCell({ value }: { value: string | null }) {
  return <Cell className="whitespace-nowrap text-muted">{value ? shortDate(value) : '—'}</Cell>
}

export function TextCell({ value, wide = false }: { value: string | null; wide?: boolean }) {
  return (
    <Cell className={wide ? 'w-full max-w-0 font-medium text-ink' : 'max-w-48 text-muted'}>
      <span className="block truncate" title={value ?? undefined}>
        {value || '—'}
      </span>
    </Cell>
  )
}

export function LinkCell({ href, clamp = false, children }: { href: string; clamp?: boolean; children: ReactNode }) {
  return (
    <Cell className={clamp ? 'max-w-48' : 'whitespace-nowrap'}>
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="block truncate text-ink underline underline-offset-4 hover:text-brand"
        title={href}
        data-testid="row-link"
      >
        {children}
      </a>
    </Cell>
  )
}
