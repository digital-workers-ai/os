import type { KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import type { CanvasNode } from '@/api'
import { Button, buttonVariants } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Pill } from '@/components/ui/pill'
import { isPicture } from '@/lib/canvas'
import { shortDate } from '@/lib/format'

function Media({ node }: { node: CanvasNode }) {
  if (isPicture(node) && node.url)
    return <img src={node.url} alt={node.label} className="max-h-[70vh] w-full rounded-lg bg-wash object-contain" data-testid="canvas-preview-image" />
  if (node.media_type === 'text/html' && node.url)
    return <iframe src={node.url} title={node.label} className="h-[70vh] w-full rounded-lg border border-line bg-paper" data-testid="canvas-preview-frame" />
  return (
    <p className="rounded-lg bg-wash p-4 text-sm text-ink" data-testid="canvas-preview-label">
      {node.label}
    </p>
  )
}

export function Preview({
  nodes,
  index,
  onStep,
  onClose,
}: {
  nodes: CanvasNode[]
  index: number | null
  onStep: (index: number) => void
  onClose: () => void
}) {
  const node = index === null ? undefined : nodes[index]
  const step = (delta: number) => {
    if (index === null) return
    const next = index + delta
    if (next >= 0 && next < nodes.length) onStep(next)
  }
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowLeft') step(-1)
    if (e.key === 'ArrowRight') step(1)
  }
  return (
    <Dialog open={!!node} onOpenChange={(open) => !open && onClose()}>
      {node && index !== null && (
        <DialogContent className="max-w-2xl" onKeyDown={onKeyDown} data-testid="canvas-preview" data-seq={node.asset_seq}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <DialogTitle className="truncate">{node.label}</DialogTitle>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                <Pill>{node.kind}</Pill>
                <Pill>{node.origin}</Pill>
                <span>{shortDate(node.date)}</span>
                <span>· v{node.version}</span>
              </div>
            </div>
            <DialogClose asChild>
              <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" data-testid="canvas-preview-close">
                <X size={16} />
              </Button>
            </DialogClose>
          </div>
          <Media node={node} />
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-8 w-8" disabled={index === 0} onClick={() => step(-1)} aria-label="previous" data-testid="canvas-preview-prev">
                <ChevronLeft size={16} />
              </Button>
              <span className="text-xs tabular-nums text-muted" data-testid="canvas-preview-position">
                {index + 1} / {nodes.length}
              </span>
              <Button variant="ghost" size="icon" className="h-8 w-8" disabled={index >= nodes.length - 1} onClick={() => step(1)} aria-label="next" data-testid="canvas-preview-next">
                <ChevronRight size={16} />
              </Button>
            </div>
            <Link to={`/assets/${node.asset_seq}`} className={buttonVariants({ variant: 'link', size: 'sm' })} data-testid="canvas-preview-open">
              Open asset
            </Link>
          </div>
        </DialogContent>
      )}
    </Dialog>
  )
}
