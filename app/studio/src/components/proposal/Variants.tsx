import type { DraftFile, Proposal } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { bytesLabel, imageDrafts } from '@/components/proposal/draft'
import { Line, Panel } from '@/components/proposal/Panel'
import { cn } from '@/lib/utils'

export const variantFiles = (proposal: Proposal): DraftFile[] => {
  const images = imageDrafts(proposal.drafts)
  return images.length > 0 ? images : proposal.drafts
}

export function Variants({
  proposal,
  files,
  picked,
  onPick,
}: {
  proposal: Proposal
  files: DraftFile[]
  picked: string[]
  onPick: (path: string) => void
}) {
  return (
    <div className="space-y-6">
      <Panel title={`Variants (${files.length})`} testId="variants">
        {files.length === 0 ? (
          <Empty testId="variants-empty">no variant drafted yet</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="variants-grid">
            {files.map((file, index) => {
              const on = picked.includes(file.path)
              return (
                <label
                  key={file.path}
                  className={cn(
                    'flex cursor-pointer flex-col gap-2 rounded-xl border p-3 transition-colors',
                    on ? 'border-ink bg-wash' : 'border-line hover:bg-wash/60',
                  )}
                  data-testid="variant-card"
                  data-path={file.path}
                  data-picked={on}
                >
                  <span className="flex aspect-square flex-col items-center justify-center gap-1 rounded-md border border-dashed border-line bg-surface p-2 text-center">
                    <span className="text-xs font-medium text-muted">v{index + 1}</span>
                    <span className="break-words text-sm font-medium text-ink">{proposal.title}</span>
                  </span>
                  <span className="flex items-center gap-2 text-xs text-muted">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => onPick(file.path)}
                      className="h-3.5 w-3.5 accent-ink"
                      aria-label={`build v${index + 1}`}
                      data-testid="variant-checkbox"
                    />
                    <Mono className="min-w-0 flex-1">{file.path}</Mono>
                    <span className="whitespace-nowrap">{bytesLabel(file.bytes)}</span>
                  </span>
                </label>
              )
            })}
          </div>
        )}
        <p className="mt-3 text-xs text-muted" data-testid="variants-note">
          drafts are the look rendered flat: the text is HTML and only the background is generated at build time.
        </p>
      </Panel>

      <Panel title="Build" testId="build-panel">
        <Line name="look">{proposal.look ?? '—'}</Line>
        <Line name="selected">
          {picked.length} of {files.length}
        </Line>
        <Line name="cost">{proposal.build_cost ?? 'not estimated'}</Line>
      </Panel>
    </div>
  )
}
