import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import type { SpyDefinition, VisibilityCheck, VisibilityCompany, VisibilityQuery, VisibilityResponse } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Pill } from '@/components/ui/pill'
import { ENGINES } from '@/lib/engines'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted'
const CELL = 'py-2 pr-4 align-middle'

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const companyNames = (definition: SpyDefinition) =>
  [definition.brand, ...definition.competitors].flatMap((company) => [company.name, ...company.aliases])

const namePattern = (names: string[]) =>
  names.length === 0 ? null : new RegExp(`(?<!\\w)(${[...names].sort((a, b) => b.length - a.length).map(escape).join('|')})(?!\\w)`, 'gi')

const engineLabel = (value: string) => ENGINES.find((engine) => engine.value === value)?.label ?? value

const bestRank = (checks: VisibilityCheck[], company: string) => {
  const ranks = checks.map((check) => check.mentions[company]).filter((rank): rank is number => rank !== undefined)
  return ranks.length === 0 ? null : Math.min(...ranks)
}

const latest = (checks: VisibilityCheck[]) => checks.map((check) => check.checked_at).reduce((a, b) => (a > b ? a : b))

function Marked({ text, pattern }: { text: string; pattern: RegExp | null }) {
  if (!pattern) return <>{text}</>
  return (
    <>
      {text.split(pattern).map((part, i) =>
        i % 2 ? (
          <mark key={i} className="rounded bg-brand/15 px-0.5 text-ink">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  )
}

function Check({ check, pattern }: { check: VisibilityCheck; pattern: RegExp | null }) {
  const ranks = Object.entries(check.mentions).sort(([, a], [, b]) => a - b)
  return (
    <div className="flex flex-col gap-2" data-engine={check.engine}>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="font-medium text-ink">{engineLabel(check.engine)}</span>
        <span>{shortDate(check.checked_at)}</span>
        <span>{num(check.sources)} sources</span>
        {ranks.map(([company, rank]) => (
          <Pill key={company}>
            {company} #{rank}
          </Pill>
        ))}
      </div>
      {check.answer ? (
        <p className="whitespace-pre-wrap text-sm text-ink">
          <Marked text={check.answer} pattern={pattern} />
        </p>
      ) : (
        <p className="text-sm italic text-muted">no answer text</p>
      )}
    </div>
  )
}

function Row({ entry, companies, pattern }: { entry: VisibilityQuery; companies: VisibilityCompany[]; pattern: RegExp | null }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <tr
        className="cursor-pointer border-b border-line/30 hover:bg-wash/50"
        onClick={() => setOpen(!open)}
        data-testid="visibility-row"
        data-query={entry.query}
      >
        <td className={CELL}>
          <button type="button" aria-expanded={open} className="flex items-center gap-1.5 text-left font-medium text-ink">
            <ChevronRight size={14} className={cn('shrink-0 text-muted transition-transform', open && 'rotate-90')} />
            {entry.query}
          </button>
        </td>
        {entry.checks.length === 0 ? (
          <td className={cn(CELL, 'text-muted')} colSpan={companies.length + 1}>
            no checks yet
          </td>
        ) : (
          <>
            {companies.map((company) => {
              const rank = bestRank(entry.checks, company.name)
              return (
                <td key={company.name} className={cn(CELL, 'whitespace-nowrap text-right tabular-nums', rank === null ? 'text-muted' : 'text-ink')}>
                  {rank === null ? '—' : `#${rank} ●`}
                </td>
              )
            })}
            <td className={cn(CELL, 'whitespace-nowrap text-right text-muted')}>{shortDate(latest(entry.checks))}</td>
          </>
        )}
      </tr>
      {open && (
        <tr className="border-b border-line/30" data-testid="visibility-expanded">
          <td colSpan={companies.length + 2} className="px-2 pb-4 pt-1">
            {entry.checks.length === 0 ? (
              <Empty>no checks yet</Empty>
            ) : (
              <div className="flex flex-col gap-4">
                {entry.checks.map((check) => (
                  <Check key={check.engine} check={check} pattern={pattern} />
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export function MentionMatrix({ data, definition }: { data: VisibilityResponse; definition: SpyDefinition }) {
  const pattern = namePattern(companyNames(definition))
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="visibility-table">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>query</th>
            {data.companies.map((company) => (
              <th key={company.name} className={cn(HEAD, 'text-right')}>
                {company.name}
                {company.role === 'brand' && ' (you)'}
              </th>
            ))}
            <th className={cn(HEAD, 'text-right')}>checked</th>
          </tr>
        </thead>
        <tbody>
          {data.queries.map((entry) => (
            <Row key={entry.query} entry={entry} companies={data.companies} pattern={pattern} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
