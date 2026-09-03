import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, get, type ApiError } from '../api'
import { SectionCard } from '@/components/SectionCard'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

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

const num = (n: number) => n.toLocaleString()
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

const relTime = (iso: string) => {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86400)}d ago`
}

const SEVERITIES = ['high', 'medium', 'low']
const severityRank = (s: string) => (SEVERITIES.includes(s) ? SEVERITIES.indexOf(s) : SEVERITIES.length)

const bySeverity = (a: Finding, b: Finding) =>
  severityRank(a.severity) - severityRank(b.severity) || a.rule.localeCompare(b.rule) || a.anchor.localeCompare(b.anchor)

type Tone = 'ok' | 'warn' | 'err' | 'unknown' | 'neutral'

const TONES: Record<Tone, string> = {
  ok: 'bg-dbb-up/10 text-dbb-up',
  warn: 'bg-amber-50 text-amber-800',
  err: 'bg-dbb-clay/10 text-dbb-clay',
  unknown: 'border border-dashed border-dbb-warm text-dbb-muted',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

const severityTone = (s: string): Tone => (s === 'high' ? 'err' : s === 'medium' ? 'warn' : 'neutral')
const verdictOf = (met: boolean | null) => (met === null ? 'unknown' : met ? 'met' : 'missed')
const verdictTone = (met: boolean | null): Tone => (met === null ? 'unknown' : met ? 'ok' : 'err')

const describe = (c: Condition) =>
  Object.entries(c)
    .filter(([k]) => k !== 'attr')
    .map(([op, v]) => `${c.attr} ${op} ${JSON.stringify(v)}`)

const formatValue = (v: unknown) =>
  Array.isArray(v) ? v.map((n) => (typeof n === 'number' ? num(n) : String(n))).join(' – ') : typeof v === 'number' ? num(v) : String(v)

function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone])}>{children}</span>
}

function Chip({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cn('inline-flex items-center rounded-full border border-dbb-warm px-2 py-0.5 text-[11px] text-dbb-muted', className)}>{children}</span>
}

function Chips({ entries }: { entries: [string, unknown][] }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <Chip key={k}>
          {k}=<span className="font-medium text-dbb-charcoal">{formatValue(v)}</span>
        </Chip>
      ))}
    </span>
  )
}

function ErrorLine({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <p role="alert" className="mb-3 text-sm text-dbb-clay">
      <span className="font-mono text-xs">{error.status || 'network'}</span> {error.detail}
    </p>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-dbb-muted">{children}</p>
}

function Inferred({ reading, sha, producedBy }: { reading?: string; sha?: string; producedBy?: string }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Pill tone="warn">inferred</Pill>
      {reading && <span className="font-mono text-xs text-dbb-charcoal">{reading}</span>}
      {sha && <span className="font-mono text-xs text-dbb-muted">{sha.slice(0, 12)}</span>}
      {producedBy && <span className="font-mono text-xs text-dbb-muted">{producedBy}</span>}
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
          <div className="mt-0.5 font-mono text-[11px] text-dbb-muted">{g.goal}</div>
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
              <span className="font-medium text-dbb-charcoal">{r.label}</span> <span className="font-mono text-xs">{name}</span>
            </TableCell>
            <TableCell>{r.entity}</TableCell>
            <TableCell>
              <Pill tone={severityTone(r.severity)}>{r.severity}</Pill>
            </TableCell>
            <TableCell>
              <span className="inline-flex flex-wrap gap-1">
                {r.all.flatMap(describe).map((text) => (
                  <Chip key={'all ' + text}>
                    all: <span className="ml-1 font-medium text-dbb-charcoal">{text}</span>
                  </Chip>
                ))}
                {r.any.flatMap(describe).map((text) => (
                  <Chip key={'any ' + text}>
                    any: <span className="ml-1 font-medium text-dbb-charcoal">{text}</span>
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
        <ErrorLine error={goalsError} />
        {!goals && !goalsError && <Muted>loading…</Muted>}
        {goals && goals.goals.length === 0 && <Muted>no goals defined</Muted>}
        {goals && goals.goals.length > 0 && (
          <div className="flex flex-col gap-4 sm:grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
        <ErrorLine error={rulesError} />
        {rules && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Muted>
              {plural(rules.rules, 'rule')} over {num(rules.report.evaluated)} entities · as of{' '}
              <span className="font-mono text-xs text-dbb-charcoal">{rules.as_of}</span> ({relTime(rules.as_of)})
            </Muted>
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
            {!rules && !rulesError && <Muted>loading…</Muted>}
            {rules && findings.length === 0 && <Muted>no findings</Muted>}
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
                        <span className="font-medium text-dbb-charcoal">{f.label}</span> <span className="font-mono text-xs">{f.rule}</span>
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
            <ErrorLine error={defsError} />
            {!defs && !defsError && <Muted>loading…</Muted>}
            {defs && <Definitions defs={defs} />}
          </TabsContent>
        </Tabs>
      </SectionCard>
    </div>
  )
}
