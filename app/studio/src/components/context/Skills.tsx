import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { asApiError, getSkill, getSkills, type Skill, type SkillsResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { fixed, num, pct } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEADING = 'mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted'
const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'

const statsLine = (skill: Skill) =>
  [
    `runs ${num(skill.runs)}`,
    `approval ${skill.approval_rate === null ? '—' : pct(skill.approval_rate)}`,
    `median edits ${skill.median_edits === null ? '—' : num(skill.median_edits)}`,
    skill.cost_per_build === null ? '— per build' : `$${fixed(skill.cost_per_build)} per build`,
  ].join(' · ')

function SkillList({
  query,
  selected,
  onSelect,
}: {
  query: UseQueryResult<SkillsResponse>
  selected: string | null
  onSelect: (name: string) => void
}) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const skills = query.data.skills
  if (skills.length === 0) return <Empty>no skills yet</Empty>
  return (
    <div className="space-y-0.5">
      {skills.map((skill) => (
        <button
          key={skill.name}
          type="button"
          aria-pressed={skill.name === selected}
          title={skill.description}
          onClick={() => onSelect(skill.name)}
          className={cn(
            'flex w-full items-baseline gap-2 rounded-md px-2 py-1 text-left text-sm text-ink transition-colors hover:bg-wash',
            skill.name === selected && 'bg-wash font-medium',
          )}
          data-testid="skill-row"
          data-name={skill.name}
        >
          <span className="min-w-0 flex-1 truncate">{skill.name}</span>
          <span className="shrink-0 tabular-nums text-muted">{num(skill.runs)}</span>
        </button>
      ))}
    </div>
  )
}

function SkillBody({ selected, query }: { selected: string | null; query: UseQueryResult<Skill> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (selected === null) return <Empty>no skill selected</Empty>
  if (!query.data) return <Loading />
  const skill = query.data
  const proposed = skill.proposed_lesson
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
        <h3 className="min-w-0 text-sm font-medium text-ink">
          {skill.name}/SKILL.md <Mono className="ml-1 text-muted">{skill.sha}</Mono>
        </h3>
        <span className="text-xs text-muted">modes: {skill.modes.join(' · ')}</span>
      </div>
      {skill.body === '' ? (
        <Empty>this skill has no body yet</Empty>
      ) : (
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink" data-testid="skill-body">
          {skill.body}
        </p>
      )}
      <div className="mt-3" data-testid="skill-lessons">
        <p className={LABEL}>lessons</p>
        {skill.lessons.length === 0 ? (
          <Empty>no lessons yet</Empty>
        ) : (
          <ul className="mt-1 space-y-0.5">
            {skill.lessons.map((lesson) => (
              <li key={lesson} className="flex items-baseline gap-2 text-sm text-ink" data-testid="skill-lesson">
                <span className="text-muted">-</span>
                <span className="min-w-0">{lesson}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {proposed && (
        <div className="mt-3 rounded-md border border-line" data-testid="skill-proposed">
          <p className={cn(LABEL, 'border-b border-line px-2 py-1')}>proposed by taste agent</p>
          <p className="bg-ok/5 px-2 py-1 font-mono text-xs text-ok">+ {proposed.line}</p>
          <div className="flex flex-wrap items-baseline gap-2 px-2 py-1 text-xs text-muted">
            <span>evidence:</span>
            {proposed.evidence.map((seq) => (
              <Link key={seq} to={`/proposals/${seq}`} className="text-ink hover:underline">
                #{seq}
              </Link>
            ))}
            <a
              href={proposed.url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-ink hover:underline"
              data-testid="skill-proposed-pr"
            >
              PR ↗
            </a>
          </div>
        </div>
      )}
      <p className="mt-3 border-t border-line/50 pt-2 text-xs text-muted" data-testid="skill-stats">
        {statsLine(skill)}
      </p>
    </div>
  )
}

export function SkillsPanel() {
  const skills = useQuery({ queryKey: ['skills'], queryFn: getSkills })
  const [picked, setPicked] = useState<string | null>(null)
  const selected = picked ?? skills.data?.skills[0]?.name ?? null
  const skill = useQuery({
    queryKey: ['skill', selected],
    queryFn: () => getSkill(selected as string),
    enabled: selected !== null,
  })
  return (
    <Card
      className="p-4 sm:p-5"
      data-testid="skills-panel"
      data-state={skills.isPending ? 'loading' : skills.error ? 'error' : 'ready'}
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]">
        <div>
          <h2 className={HEADING}>.claude/skills/dw-*</h2>
          <SkillList query={skills} selected={selected} onSelect={setPicked} />
        </div>
        <SkillBody selected={selected} query={skill} />
      </div>
    </Card>
  )
}
