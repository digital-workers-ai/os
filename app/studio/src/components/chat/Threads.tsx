import { Link } from 'react-router-dom'
import type { ThreadRow } from '@/api'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

export function Threads({
  threads,
  current,
  onNew,
  creating,
}: {
  threads: ThreadRow[]
  current: number | null
  onNew: () => void
  creating: boolean
}) {
  return (
    <aside className="flex flex-col gap-2" data-testid="threads">
      <Button size="sm" onClick={onNew} disabled={creating} data-testid="thread-new">
        + new
      </Button>
      {threads.length === 0 ? (
        <Empty testId="threads-empty">no threads yet</Empty>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {threads.map((thread) => (
            <li key={thread.seq}>
              <Link
                to={`/create/${thread.seq}`}
                aria-current={thread.seq === current ? 'page' : undefined}
                className={cn(
                  'flex flex-col rounded-lg px-3 py-2 text-sm transition-colors',
                  thread.seq === current ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:bg-black/[0.04]',
                )}
                data-testid="thread-row"
                data-seq={thread.seq}
              >
                <span className="truncate">{thread.title || 'untitled'}</span>
                <span className="text-[11px] text-muted">{shortDate(thread.created_at.slice(0, 10))}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
