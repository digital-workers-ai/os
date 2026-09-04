import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { Inferred } from '@/components/Inferred'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Chip, Pill, type Tone } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, plural, when } from '@/lib/format'

interface Finding {
  rule: string
  label: string
  severity: string
  entity_type: string
  canonical_id: string
  anchor: string
  company: string | null
  evidence: Record<string, string>
}

interface RulesResponse {
  as_of: string
  rules: number
  findings: Finding[]
  by_severity: Record<string, number>
  report: { evaluated: number; unreadable: Record<string, number> }
}

interface Goal {
  goal: string
  label: string
  metric?: string
  target?: number
  strategy?: string
  current?: number | null
  met: boolean | null
  progress?: number | null
  entities?: number
  unknown?: string
  error?: string
  band?: number[]
  outside_band_by?: number
  trend?: string
  inferred?: boolean
  reading?: string
  vocabulary_sha?: string
  produced_by?: string[]
}

interface GoalsResponse {
  goals: Goal[]
  met: number
  missed: number
  unknown: number
}

const SEVERITIES = ['high', 'medium', 'low']
const severityRank = (s: string) => (SEVERITIES.includes(s) ? SEVERITIES.indexOf(s) : SEVERITIES.length)

const bySeverity = (a: Finding, b: Finding) =>
  severityRank(a.severity) - severityRank(b.severity) || a.rule.localeCompare(b.rule) || a.anchor.localeCompare(b.anchor)

const severityTone = (s: string): Tone => (s === 'high' ? 'err' : s === 'medium' ? 'warn' : 'neutral')
const verdictOf = (met: boolean | null) => (met === null ? 'unknown' : met ? 'met' : 'missed')
const verdictTone = (met: boolean | null): Tone => (met === null ? 'unknown' : met ? 'ok' : 'err')

const formatValue = (v: unknown) =>
  Array.isArray(v) ? v.map((n) => (typeof n === 'number' ? num(n) : String(n))).join(' – ') : typeof v === 'number' ? num(v) : String(v)

function Chips({ entries, stack = false }: { entries: [string, unknown][]; stack?: boolean }) {
  return (
    <span className={stack ? 'flex flex-col items-start gap-1' : 'inline-flex flex-wrap gap-1'}>
      {entries.map(([k, v]) => (
        <Chip key={k}>
          {k}=<strong>{formatValue(v)}</strong>
        </Chip>
      ))}
    </span>
  )
}

const goalDetail = (g: Goal): [string, unknown][] => {
  const detail: [string, unknown][] = []
  if (g.band) detail.push(['band', g.band])
  if (g.outside_band_by !== undefined) detail.push(['outside_band_by', g.outside_band_by])
  if (g.trend) detail.push(['trend', g.trend])
  return detail
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
      <Table data-testid="goals-table">
        <TableHeader>
          <TableRow>
            <TableHead>Goal ({num(goals.length)})</TableHead>
            <TableHead>Metric</TableHead>
            <TableHead className="text-right">Target</TableHead>
            <TableHead className="text-right">Current</TableHead>
            <TableHead>Verdict</TableHead>
            <TableHead>Progress</TableHead>
            <TableHead>Detail</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.map((g) => {
            const detail = goalDetail(g)
            return (
              <TableRow key={g.goal}>
                <TableCell>
                  <span className="block font-medium text-dbb-charcoal">{g.label}</span>
                  <Mono className="block">{g.goal}</Mono>
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {g.metric ? <Mono className="block">{g.metric}</Mono> : '—'}
                  {g.strategy && <span className="block">{g.strategy}</span>}
                </TableCell>
                <TableCell className="text-right tabular-nums">{g.target === undefined ? '—' : num(g.target)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {g.current === null || g.current === undefined ? <Pill tone="unknown">unknown</Pill> : num(g.current)}
                </TableCell>
                <TableCell>
                  <Pill tone={verdictTone(g.met)}>{verdictOf(g.met)}</Pill>
                </TableCell>
                <TableCell>
                  {typeof g.progress === 'number' && (
                    <span className="inline-flex items-center gap-2">
                      <span className="block h-1.5 w-24 rounded-full bg-dbb-sand">
                        <span className="block h-full rounded-full bg-dbb-charcoal" style={{ width: `${Math.max(0, Math.min(100, g.progress))}%` }} />
                      </span>
                      <span className="text-xs tabular-nums">{num(g.progress)}%</span>
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <span className="inline-flex flex-wrap items-center gap-1.5">
                    {detail.length > 0 && <Chips entries={detail} stack />}
                    {g.unknown && <span className="text-xs">{g.unknown}</span>}
                    {g.error && <span className="text-xs text-dbb-clay">{g.error}</span>}
                    {g.inferred && <Inferred reading={g.reading} sha={g.vocabulary_sha} producedBy={g.produced_by?.join(', ')} />}
                  </span>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <Pager offset={offset} count={page.length} total={goals.length} onPage={setOffset} size={size} allSize={goals.length} onSize={changeSize} />
    </>
  )
}

export function Insights() {
  const [rules, setRules] = useState<RulesResponse | null>(null)
  const [rulesError, setRulesError] = useState<ApiError | null>(null)
  const [goals, setGoals] = useState<GoalsResponse | null>(null)
  const [goalsError, setGoalsError] = useState<ApiError | null>(null)
  const [findingsOffset, setFindingsOffset] = useState(0)
  const [findingsSize, setFindingsSize] = useState(PAGE)
  const changeFindingsSize = (n: number) => {
    setFindingsSize(n)
    setFindingsOffset(0)
  }

  const loadRules = () =>
    get<RulesResponse>('/api/insights/rules')
      .then((r) => {
        setRules(r)
        setRulesError(null)
      })
      .catch((e) => setRulesError(asApiError(e)))

  const loadGoals = () =>
    get<GoalsResponse>('/api/insights/goals')
      .then((r) => {
        setGoals(r)
        setGoalsError(null)
      })
      .catch((e) => setGoalsError(asApiError(e)))

  useEffect(() => {
    loadRules()
    loadGoals()
  }, [])

  useEffect(() => {
    setFindingsOffset(0)
    setFindingsSize(PAGE)
  }, [rules])

  const findings = rules ? [...rules.findings].sort(bySeverity) : []
  const findingsPage = findings.slice(findingsOffset, findingsOffset + findingsSize)
  const unreadable = Object.entries(rules?.report.unreadable ?? {})
  const unreadableTotal = unreadable.reduce((sum, [, n]) => sum + n, 0)

  return (
    <div className="space-y-6">
      <SectionCard
        title="Goals"
        testId="goals"
        headerRight={
          goals && (
            <div className="flex flex-wrap gap-1.5" data-testid="goals-pills">
              <Pill tone="ok">{num(goals.met)} met</Pill>
              <Pill tone="err">{num(goals.missed)} missed</Pill>
              <Pill tone="unknown">{num(goals.unknown)} unknown</Pill>
            </div>
          )
        }
      >
        <ErrorBanner error={goalsError} className="mb-3" />
        {!goals && !goalsError && <Loading />}
        {goals && goals.goals.length === 0 && <Empty>no goals defined</Empty>}
        {goals && goals.goals.length > 0 && <GoalsTable goals={goals.goals} />}
      </SectionCard>

      <SectionCard
        title="Findings"
        testId="findings"
        headerRight={
          rules && (
            <div className="flex flex-wrap gap-1.5" data-testid="findings-pills">
              {Object.entries(rules.by_severity).map(([s, n]) => (
                <Pill key={s} tone={severityTone(s)}>
                  {num(n)} {s}
                </Pill>
              ))}
            </div>
          )
        }
      >
        <ErrorBanner error={rulesError} className="mb-3" />
        {rules && unreadable.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-1.5" data-testid="findings-unreadable">
            <span className="text-sm text-dbb-muted">{num(unreadableTotal)} values unreadable</span>
            {unreadable.map(([key, n]) => (
              <Chip key={key} className="border-amber-200 bg-amber-50 text-amber-800">
                {num(n)} × {key}
              </Chip>
            ))}
          </div>
        )}
        {!rules && !rulesError && <Loading />}
        {rules && findings.length === 0 && <Empty>no findings</Empty>}
        {findings.length > 0 && (
          <>
            <Table className="table-fixed" data-testid="findings-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20">Severity ({num(findings.length)})</TableHead>
                  <TableHead className="w-[368px]">Rule</TableHead>
                  <TableHead className="w-28">Entity</TableHead>
                  <TableHead className="w-28">Company</TableHead>
                  <TableHead className="w-60">Evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {findingsPage.map((f) => (
                  <TableRow key={f.rule + f.canonical_id}>
                    <TableCell>
                      <Pill tone={severityTone(f.severity)}>{f.severity}</Pill>
                    </TableCell>
                    <TableCell>
                      <span className="block font-medium text-dbb-charcoal">{f.label}</span>
                      <Mono className="block">{f.rule}</Mono>
                    </TableCell>
                    <TableCell>
                      <Pill>{f.entity_type}</Pill>
                    </TableCell>
                    <TableCell>{f.company ?? '—'}</TableCell>
                    <TableCell>
                      <Chips entries={Object.entries(f.evidence)} stack />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pager
              offset={findingsOffset}
              count={findingsPage.length}
              total={findings.length}
              onPage={setFindingsOffset}
              size={findingsSize}
              allSize={findings.length}
              onSize={changeFindingsSize}
            />
          </>
        )}
      </SectionCard>
    </div>
  )
}
