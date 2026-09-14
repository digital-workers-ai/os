import type { ReactNode } from 'react'
import type { DraftFile, Proposal } from '@/api'
import { Button } from '@/components/ui/button'
import { Mono } from '@/components/ui/mono'
import { bytesLabel } from '@/components/proposal/draft'
import { Panel } from '@/components/proposal/Panel'

const FRAME = 'overflow-hidden rounded-xl border border-line bg-paper shadow-sm'

function Body({ text, title, drafts }: { text: string | null; title: string; drafts: DraftFile[] }) {
  if (text !== null)
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink" data-testid="preview-body">
        {text}
      </p>
    )
  return (
    <div className="space-y-1" data-testid="preview-placeholder">
      <p className="text-sm font-medium text-ink">{title}</p>
      {drafts.length === 0 ? (
        <p className="text-xs text-muted">no draft file written yet</p>
      ) : (
        drafts.map((file) => (
          <p key={file.path} className="text-xs text-muted">
            <Mono>{file.path}</Mono> · {file.media_type} · {bytesLabel(file.bytes)}
          </p>
        ))
      )}
    </div>
  )
}

function LinkedIn({ children }: { children: ReactNode }) {
  return (
    <div className={FRAME} data-testid="preview-linkedin">
      <div className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-[11px] font-medium text-paper">DW</span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-ink">Digital Workers</span>
          <span className="block text-xs text-muted">1h · edited</span>
        </span>
      </div>
      <div className="px-4 py-3">{children}</div>
      <div className="border-t border-line/60 px-4 py-2 text-xs text-muted">♡ 0 · 💬 0 · ↻ 0</div>
    </div>
  )
}

function Email({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={FRAME} data-testid="preview-email">
      <div className="space-y-0.5 border-b border-line/60 bg-wash px-4 py-3 text-xs text-muted">
        <p>
          From <span className="text-ink">Digital Workers</span>
        </p>
        <p>To subscribers</p>
        <p>
          Subject <span className="font-medium text-ink">{title}</span>
        </p>
      </div>
      <div className="px-4 py-4">{children}</div>
      <div className="border-t border-line/60 px-4 py-2 text-xs text-muted">unsubscribe · view in browser</div>
    </div>
  )
}

function Article({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={FRAME} data-testid="preview-article">
      <div className="border-b border-line/60 px-5 py-4">
        <h4 className="text-lg font-medium leading-snug text-ink">{title}</h4>
        <p className="mt-1 text-xs text-muted">Digital Workers · draft</p>
      </div>
      <div className="px-5 py-4 leading-relaxed">{children}</div>
    </div>
  )
}

export function Preview({ proposal, text, onEdit }: { proposal: Proposal; text: string | null; onEdit: () => void }) {
  const body = <Body text={text} title={proposal.title} drafts={proposal.drafts} />
  const platform = proposal.kind === 'newsletter' ? 'email' : proposal.kind === 'blog' ? 'article' : 'LinkedIn'
  return (
    <Panel title={`Preview (${platform})`} testId="preview-pane">
      {proposal.kind === 'newsletter' ? (
        <Email title={proposal.title}>{body}</Email>
      ) : proposal.kind === 'blog' ? (
        <Article title={proposal.title}>{body}</Article>
      ) : (
        <LinkedIn>{body}</LinkedIn>
      )}
      <div className="mt-3">
        <Button size="sm" onClick={onEdit} data-testid="edit-draft-btn">
          Edit draft
        </Button>
      </div>
    </Panel>
  )
}
