import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '../api'
import { Json } from '../components/Json'
import { Empty, Panel, num, relTime } from '../components/Panel'
import { Status } from '../components/Status'
import './Insights.css'

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

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

const SEVERITIES = ['high', 'medium', 'low']
const severityRank = (s: string) => (SEVERITIES.includes(s) ? SEVERITIES.indexOf(s) : SEVERITIES.length)
const severityClass = (s: string) => (s === 'high' ? 'err' : s === 'medium' ? 'warn' : '')

const bySeverity = (a: Finding, b: Finding) =>
  severityRank(a.severity) - severityRank(b.severity) || a.rule.localeCompare(b.rule) || a.anchor.localeCompare(b.anchor)

const verdictOf = (met: boolean | null) => (met === null ? 'unknown' : met ? 'met' : 'missed')
const verdictClass = (met: boolean | null) => (met === null ? 'unknown' : met ? 'ok' : 'err')

const describe = (c: Condition) =>
  Object.entries(c)
    .filter(([k]) => k !== 'attr')
    .map(([op, v]) => `${c.attr} ${op} ${JSON.stringify(v)}`)

function Chips({ entries }: { entries: [string, unknown][] }) {
  return (
    <span className="chips">
      {entries.map(([k, v]) => (
        <span key={k} className="chip">
          {k}=<strong>{Array.isArray(v) ? v.map((n) => (typeof n === 'number' ? num(n) : String(n))).join(' – ') : typeof v === 'number' ? num(v) : String(v)}</strong>
        </span>
      ))}
    </span>
  )
}

function Definitions({ defs }: { defs: DefinitionsResponse }) {
  const entries = Object.entries(defs.rules)
  return (
    <details className="definitions">
      <summary>rule definitions ({entries.length})</summary>
      <table>
        <thead>
          <tr>
            <th>Rule</th>
            <th>Entity</th>
            <th>Severity</th>
            <th>Conditions</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, r]) => (
            <tr key={name}>
              <td>
                <strong>{r.label}</strong> <code className="dim">{name}</code>
              </td>
              <td>{r.entity}</td>
              <td>
                <span className={'pill ' + severityClass(r.severity)}>{r.severity}</span>
              </td>
              <td>
                <span className="chips">
                  {r.all.flatMap(describe).map((text) => (
                    <span key={'all ' + text} className="chip">
                      all: <strong>{text}</strong>
                    </span>
                  ))}
                  {r.any.flatMap(describe).map((text) => (
                    <span key={'any ' + text} className="chip">
                      any: <strong>{text}</strong>
                    </span>
                  ))}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="panel-body">
        <Json value={defs.rules} label="raw definitions" />
      </div>
    </details>
  )
}

function GoalDetail({ g }: { g: Goal }) {
  const detail: [string, unknown][] = []
  if (g.band) detail.push(['band', g.band])
  if (g.outside_band_by !== undefined) detail.push(['outside_band_by', g.outside_band_by])
  if (g.trend) detail.push(['trend', g.trend])
  return (
    <>
      {detail.length > 0 && <Chips entries={detail} />}
      {g.unknown && <span className="reason">{g.unknown}</span>}
      {g.error && <span className="reason err">{g.error}</span>}
    </>
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
    <>
      <Panel
        title={`Findings${rules ? ` (${findings.length})` : ''}`}
        actions={
          <button className="btn" onClick={loadRules}>
            Refresh
          </button>
        }
      >
        <div className="panel-body">
          <Status error={rulesError} />
          {rules && (
            <>
              <p>
                {plural(rules.rules, 'rule')} over {num(rules.report.evaluated)} entities · as of <code>{rules.as_of}</code>{' '}
                <span className="dim">({relTime(rules.as_of)})</span>
              </p>
              <div className="chips">
                {Object.entries(rules.by_severity).map(([s, n]) => (
                  <span key={s} className="chip">
                    <span className={'pill ' + severityClass(s)}>{s}</span> <strong>{num(n)}</strong>
                  </span>
                ))}
              </div>
              {unreadable.length > 0 && (
                <>
                  <h3>{num(unreadableTotal)} values unreadable</h3>
                  <div className="chips">
                    {unreadable.map(([key, n]) => (
                      <span key={key} className="chip">
                        {num(n)} × <strong>{key}</strong>
                      </span>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
        {!rules && !rulesError && <Empty>loading…</Empty>}
        {rules && findings.length === 0 && <Empty>no findings</Empty>}
        {findings.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Rule</th>
                <th>Entity</th>
                <th>Anchor</th>
                <th>Company</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.rule + f.canonical_id}>
                  <td>
                    <span className={'pill ' + severityClass(f.severity)}>{f.severity}</span>
                  </td>
                  <td>
                    <strong>{f.label}</strong> <code className="dim">{f.rule}</code>
                  </td>
                  <td>{f.entity_type}</td>
                  <td>
                    <code>{f.anchor}</code>
                  </td>
                  <td>{f.company ?? <span className="dim">—</span>}</td>
                  <td>
                    <Chips entries={Object.entries(f.evidence)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="panel-body">
          <Status error={defsError} />
        </div>
        {defs && <Definitions defs={defs} />}
      </Panel>

      <Panel
        title={`Goals${goals ? ` (${goals.goals.length})` : ''}`}
        actions={
          <button className="btn" onClick={loadGoals}>
            Refresh
          </button>
        }
      >
        <div className="panel-body">
          <Status error={goalsError} />
          {goals && (
            <div className="chips">
              <span className="chip">
                <span className="pill ok">met</span> <strong>{num(goals.met)}</strong>
              </span>
              <span className="chip">
                <span className="pill err">missed</span> <strong>{num(goals.missed)}</strong>
              </span>
              <span className="chip">
                <span className="pill unknown">unknown</span> <strong>{num(goals.unknown)}</strong>
              </span>
            </div>
          )}
        </div>
        {!goals && !goalsError && <Empty>loading…</Empty>}
        {goals && goals.goals.length === 0 && <Empty>no goals defined</Empty>}
        {goals && goals.goals.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Goal</th>
                <th>Metric</th>
                <th>Strategy</th>
                <th className="num">Target</th>
                <th className="num">Current</th>
                <th>Verdict</th>
                <th>Progress</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {goals.goals.map((g) => (
                <tr key={g.goal}>
                  <td>
                    <strong>{g.label}</strong> <code className="dim">{g.goal}</code>
                  </td>
                  <td>
                    {g.metric ? <code>{g.metric}</code> : <span className="dim">—</span>}
                    {g.inferred && (
                      <>
                        {' '}
                        <span className="inferred">
                          <span className="pill warn">inferred</span>
                          {g.reading && <code>{g.reading}</code>}
                          {g.vocabulary_sha && <code className="dim">{g.vocabulary_sha.slice(0, 12)}</code>}
                          {g.produced_by && g.produced_by.length > 0 && <code className="dim">{g.produced_by.join(', ')}</code>}
                        </span>
                      </>
                    )}
                  </td>
                  <td>{g.strategy ?? <span className="dim">—</span>}</td>
                  <td className="num">{g.target === undefined ? '—' : num(g.target)}</td>
                  <td className="num">
                    {g.current === null || g.current === undefined ? <span className="pill unknown">unknown</span> : num(g.current)}
                  </td>
                  <td>
                    <span className={'pill ' + verdictClass(g.met)}>{verdictOf(g.met)}</span>
                  </td>
                  <td>
                    {typeof g.progress === 'number' ? (
                      <span className="progress">
                        <span className="bar">
                          <span style={{ width: `${Math.max(0, Math.min(100, g.progress))}%` }} />
                        </span>
                        {num(g.progress)}%
                      </span>
                    ) : (
                      <span className="dim">—</span>
                    )}
                  </td>
                  <td>
                    <GoalDetail g={g} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  )
}
