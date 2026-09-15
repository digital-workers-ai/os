import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { asApiError, getSkillRun, rebuildAsset, type ToolCall } from '@/api'
import { Section } from '@/components/assets/Section'
import { durationLabel } from '@/components/assets/stamp'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { fixed } from '@/lib/format'

const NOTE_FIELD =
  'w-full rounded-md border border-line bg-paper p-2 text-sm text-ink placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'

const toolLine = (calls: ToolCall[]) => {
  const counts = new Map<string, number>()
  for (const call of calls) counts.set(call.tool, (counts.get(call.tool) ?? 0) + 1)
  return [...counts].map(([tool, count]) => `${tool} ×${count}`).join(' · ')
}

export function Build({ seq, skillRunSeq }: { seq: number; skillRunSeq: number | null }) {
  const [note, setNote] = useState('')
  const client = useQueryClient()
  const run = useQuery({
    queryKey: ['skill-run', skillRunSeq],
    queryFn: () => getSkillRun(skillRunSeq as number),
    enabled: skillRunSeq !== null,
  })
  const rebuild = useMutation({
    mutationFn: () => rebuildAsset(seq, note),
    onSuccess: () => {
      setNote('')
      client.invalidateQueries({ queryKey: ['asset', seq] })
    },
  })
  const data = run.data
  const tools = data ? toolLine(data.tool_calls) : ''

  return (
    <Section title="Build" testId="asset-build">
      {skillRunSeq === null ? (
        <p className="text-sm text-muted">no skill run recorded</p>
      ) : (
        <>
          <p className="text-sm text-ink">
            skill run #{skillRunSeq}
            {data && ` · mode ${data.mode} · ${durationLabel(data.duration_ms)} · $${fixed(data.cost_usd)}`}
          </p>
          {tools !== '' && <p className="mt-1 text-xs text-muted">tools: {tools}</p>}
        </>
      )}
      <div className="mt-3 space-y-2">
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          placeholder="what should change…"
          aria-label="rebuild note"
          className={NOTE_FIELD}
          data-testid="asset-rebuild-note"
        />
        <Button
          size="sm"
          disabled={rebuild.isPending || note.trim() === ''}
          onClick={() => rebuild.mutate()}
          data-testid="rebuild-btn"
        >
          {rebuild.isPending ? 'Rebuilding…' : 'Rebuild with note'}
        </Button>
        {rebuild.error && <ErrorBanner error={asApiError(rebuild.error)} testId="rebuild-error" />}
      </div>
    </Section>
  )
}
