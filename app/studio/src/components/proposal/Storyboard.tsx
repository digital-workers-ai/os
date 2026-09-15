import type { LookRow, Proposal } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { ClaimRows } from '@/components/proposal/Claims'
import { bytesLabel, draftText, namedDraft } from '@/components/proposal/draft'
import { Line, Panel } from '@/components/proposal/Panel'

const frameRatio = (ratio: string | undefined) => (ratio && ratio.includes(':') ? ratio.replace(':', ' / ') : '9 / 16')

export function Storyboard({ proposal, look }: { proposal: Proposal; look: LookRow | undefined }) {
  const scenes = look?.scenes ?? []
  const content = namedDraft(proposal.drafts, 'content')
  const script = namedDraft(proposal.drafts, 'script')
  const scriptText = draftText(script)
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel title="Storyboard" testId="storyboard">
        {scenes.length === 0 ? (
          <Empty testId="storyboard-empty">{look ? 'the look lists no scenes' : 'the look is not loaded'}</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="storyboard-grid">
            {scenes.map((scene, index) => (
              <div
                key={scene}
                style={{ aspectRatio: frameRatio(look?.ratio) }}
                className="flex flex-col justify-between rounded-md border border-line bg-wash p-2 text-xs"
                data-testid="scene-card"
                data-scene={scene}
              >
                <span className="tabular-nums text-muted">{index + 1}</span>
                <span className="break-words font-medium text-ink">{scene}</span>
              </div>
            ))}
          </div>
        )}
        <p className="mt-2 text-xs text-muted">storyboard, drafted from the look's preview frames</p>
      </Panel>

      <div className="space-y-6">
        <Panel title={`content.yaml · ${scenes.length} scenes`} testId="scene-list">
          {content === null ? (
            <p className="text-xs text-muted">no content.yaml in the draft</p>
          ) : (
            <p className="mb-2 text-xs text-muted">
              <Mono>{content.path}</Mono> · {bytesLabel(content.bytes)}
            </p>
          )}
          {scenes.length === 0 ? (
            <Empty testId="scene-list-empty">no scene list</Empty>
          ) : (
            <ol className="divide-y divide-line/30">
              {scenes.map((scene, index) => (
                <li key={scene} className="flex gap-2 py-1 text-sm" data-testid="scene-row">
                  <span className="w-4 shrink-0 tabular-nums text-muted">{index + 1}</span>
                  <span className="min-w-0 flex-1 text-ink">{scene}</span>
                </li>
              ))}
            </ol>
          )}
          <p className="mb-1 mt-3 text-xs uppercase tracking-wide text-muted">stated numbers</p>
          <ClaimRows claims={proposal.claims} />
        </Panel>

        <Panel title="Script (avatar)" testId="script-panel">
          {scriptText === null ? (
            <p className="text-sm text-muted">{script === null ? 'no script in the draft' : <Mono>{script.path}</Mono>}</p>
          ) : (
            <p className="whitespace-pre-wrap break-words text-sm text-ink">{scriptText}</p>
          )}
        </Panel>

        <Panel title="Build" testId="build-panel">
          <Line name="look">{proposal.look ?? '—'}</Line>
          <Line name="ratio">{look?.ratio ?? '—'}</Line>
          <Line name="limits">
            {look?.limits_measured ? (
              <>
                {look.limits_measured} <span className="text-ok">✓</span>
              </>
            ) : (
              <span className="text-muted">not measured for this look</span>
            )}
          </Line>
          <Line name="renders">{proposal.build_cost ?? look?.build_cost ?? 'not estimated'}</Line>
        </Panel>
      </div>
    </div>
  )
}
