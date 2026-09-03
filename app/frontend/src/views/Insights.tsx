import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { Inferred } from '@/components/Inferred'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill, type Tone } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num, plural, relTime } from '@/lib/format'

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

type Condition = { attr: string } & Record<string, unknown>

interface RuleDefinition {
  label: string
  entity: string
  severity: string
  all: Condition[]
  any: Condition[]
}

interface DefinitionsResponse {
  rules: Record<string, RuleDefinition>
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

const describe = (c: Condition) =>
  Object.entries(c)
    .filter(([k]) => k !== 'attr')
    .map(([op, v]) => `${c.attr} ${op} ${JSON.stringify(v)}`)

const formatValue = (v: unknown) =>
  Array.isArray(v) ? v.map((n) => (typeof n === 'number' ? num(n) : String(n))).join(' – ') : typeof v === 'number' ? num(v) : String(v)

function Chips({ entries }: { entries: [string, unknown][] }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <Chip key={k}>
          {k}=<strong>{formatValue(v)}</strong>
        </Chip>
      ))}
    </span>
  )
}

function GoalCard({ g }: { g: Goal }) {
  const detail: [string, unknown][] = []
  if (g.band) detail.push(['band', g.band])
  if (g.outside_band_by !== undefined) detail.push(['outside_band_by', g.outside_band_by])
  if (g.trend) detail.push(['trend', g.trend])
  return (
    <Card className="flex flex-col gap-3 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold leading-snug text-dbb-charcoal">{g.label}</div>
          <Mono className="mt-0.5 block text-[11px] text-dbb-muted">{g.goal}</Mono>
        </div>
        <Pill tone={verdictTone(g.met)}>{verdictOf(g.met)}</Pill>
      </div>
      <div>
        <div className="flex items-baseline gap-1.5">
          {g.current === null || g.current === undefined ? (
            <Pill tone="unknown">unknown</Pill>
          ) : (
            <span className="text-2xl font-semibold tabular-nums text-dbb-charcoal">{num(g.current)}</span>
          )}
          <span className="text-sm text-dbb-muted">/ {g.target === undefined ? '—' : num(g.target)}</span>
        </div>
        <div className="mt-0.5 text-xs text-dbb-muted">
          {g.metric ? <span className="font-mono">{g.metric}</span> : '—'}
          {g.strategy && ` · ${g.strategy}`}
        </div>
      </div>
      {typeof g.progress === 'number' && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-dbb-sand">
            <div className="h-full rounded-full bg-dbb-charcoal" style={{ width: `${Math.max(0, Math.min(100, g.progress))}%` }} />
          </div>
          <span className="text-xs tabular-nums text-dbb-muted">{num(g.progress)}%</span>
        </div>
      )}
      {detail.length > 0 && <Chips entries={detail} />}
      {g.unknown && <p className="text-xs text-dbb-muted">{g.unknown}</p>}
      {g.error && <p className="text-xs text-dbb-clay">{g.error}</p>}
      {g.inferred && <Inferred reading={g.reading} sha={g.vocabulary_sha} producedBy={g.produced_by?.join(', ')} />}
    </Card>
  )
}

function Definitions({ defs }: { defs: DefinitionsResponse }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Rule</TableHead>
          <TableHead>Entity</TableHead>
          <TableHead>Severity</TableHead>
          <TableHead>Conditions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(defs.rules).map(([name, r]) => (
          <TableRow key={name}>
            <TableCell>
              <span className="font-medium text-dbb-charcoal">{r.label}</span> <Mono>{name}</Mono>
            </TableCell>
            <TableCell>{r.entity}</TableCell>
            <TableCell>
              <Pill tone={severityTone(r.severity)}>{r.severity}</Pill>
            </TableCell>
            <TableCell>
              <span className="inline-flex flex-wrap gap-1">
                {r.all.flatMap(describe).map((text) => (
                  <Chip key={'all ' + text}>
                    all: <strong>{text}</strong>
                  </Chip>
                ))}
                {r.any.flatMap(describe).map((text) => (
                  <Chip key={'any ' + text}>
                    any: <strong>{text}</strong>
                  </Chip>
                ))}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function Insights() {
  const [rules, setRules] = useState<RulesResponse | null>(null)
  const [rulesError, setRulesError] = useState<ApiError | null>(null)
  const [defs, setDefs] = useState<DefinitionsResponse | null>(null)
  const [defsError, setDefsError] = useState<ApiError | null>(null)
  const [goals, setGoals] = useState<GoalsResponse | null>(null)
  const [goalsError, setGoalsError] = useState<ApiError | null>(null)

  const loadRules = () =>
    get<RulesResponse>('/api/insights/rules')
      .then((r) => {
        setRules(r)
        setRulesError(null)
      })
      .catch((e) => setRulesError(asApiError(e)))

  const loadDefs = () =>
    get<DefinitionsResponse>('/api/insights/rules/definitions')
      .then((r) => {
        setDefs(r)
        setDefsError(null)
      })
      .catch((e) => setDefsError(asApiError(e)))

  const loadGoals = () =>
    get<GoalsResponse>('/api/insights/goals')
      .then((r) => {
        setGoals(r)
        setGoalsError(null)
      })
      .catch((e) => setGoalsError(asApiError(e)))

  useEffect(() => {
    loadRules()
    loadDefs()
    loadGoals()
  }, [])

  const findings = rules ? [...rules.findings].sort(bySeverity) : []
  const unreadable = Object.entries(rules?.report.unreadable ?? {})
  const unreadableTotal = unreadable.reduce((sum, [, n]) => sum + n, 0)

  return (
    <div className="space-y-6">
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h2 className="text-base font-semibold text-dbb-charcoal">Goals{goals ? ` (${goals.goals.length})` : ''}</h2>
          {goals && (
            <div className="flex flex-wrap gap-1.5">
              <Pill tone="ok">{num(goals.met)} met</Pill>
              <Pill tone="err">{num(goals.missed)} missed</Pill>
              <Pill tone="unknown">{num(goals.unknown)} unknown</Pill>
            </div>
          )}
          <Button variant="outline" size="sm" className="ml-auto" onClick={loadGoals}>
            Refresh
          </Button>
        </div>
        <ErrorBanner error={goalsError} className="mb-3" />
        {!goals && !goalsError && <Empty>loading…</Empty>}
        {goals && goals.goals.length === 0 && <Empty>no goals defined</Empty>}
        {goals && goals.goals.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {goals.goals.map((g) => (
              <GoalCard key={g.goal} g={g} />
            ))}
          </div>
        )}
      </section>

      <SectionCard
        title={`Findings${rules ? ` (${findings.length})` : ''}`}
        headerRight={
          <Button variant="outline" size="sm" onClick={loadRules}>
            Refresh
          </Button>
        }
      >
        <ErrorBanner error={rulesError} className="mb-3" />
        {rules && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="text-sm text-dbb-muted">
              {plural(rules.rules, 'rule')} over {num(rules.report.evaluated)} entities · as of{' '}
              <Mono className="text-dbb-charcoal">{rules.as_of}</Mono> ({relTime(rules.as_of)})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(rules.by_severity).map(([s, n]) => (
                <Pill key={s} tone={severityTone(s)}>
                  {num(n)} {s}
                </Pill>
              ))}
            </div>
            {unreadable.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-sm text-dbb-muted">{num(unreadableTotal)} values unreadable</span>
                {unreadable.map(([key, n]) => (
                  <Chip key={key} className="border-amber-200 bg-amber-50 text-amber-800">
                    {num(n)} × {key}
                  </Chip>
                ))}
              </div>
            )}
          </div>
        )}
        <Tabs defaultValue="findings">
          <TabsList className="mt-4">
            <TabsTrigger value="findings">Findings</TabsTrigger>
            <TabsTrigger value="definitions">Rule definitions{defs ? ` (${Object.keys(defs.rules).length})` : ''}</TabsTrigger>
          </TabsList>
          <TabsContent value="findings">
            {!rules && !rulesError && <Empty>loading…</Empty>}
            {rules && findings.length === 0 && <Empty>no findings</Empty>}
            {findings.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Severity</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Anchor</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Evidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {findings.map((f) => (
                    <TableRow key={f.rule + f.canonical_id}>
                      <TableCell>
                        <Pill tone={severityTone(f.severity)}>{f.severity}</Pill>
                      </TableCell>
                      <TableCell>
                        <span className="font-medium text-dbb-charcoal">{f.label}</span> <Mono>{f.rule}</Mono>
                      </TableCell>
                      <TableCell>{f.entity_type}</TableCell>
                      <TableCell className="whitespace-nowrap font-mono text-xs">{f.anchor}</TableCell>
                      <TableCell>{f.company ?? '—'}</TableCell>
                      <TableCell>
                        <Chips entries={Object.entries(f.evidence)} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>
          <TabsContent value="definitions">
            <ErrorBanner error={defsError} className="mb-3" />
            {!defs && !defsError && <Empty>loading…</Empty>}
            {defs && <Definitions defs={defs} />}
          </TabsContent>
        </Tabs>
      </SectionCard>
    </div>
  )
}
