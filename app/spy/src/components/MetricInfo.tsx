import type { ReactNode } from 'react'
import { ExternalLink, X } from 'lucide-react'
import type { MetricCardSpec, MetricResponse } from '@/api'
import { Button, buttonVariants } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { consoleUrl } from '@/lib/console'
import { num, shortDate } from '@/lib/format'

export interface Opened {
  card: MetricCardSpec
  last?: MetricResponse
}

function Row({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 text-sm">
      <dt className="w-24 shrink-0 text-muted">{name}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

export function MetricInfo({ open, onClose }: { open: Opened | null; onClose: () => void }) {
  const last = open?.last
  return (
    <Dialog open={!!open} onOpenChange={(shown) => !shown && onClose()}>
      <DialogContent aria-describedby={undefined} data-testid="definition">
        {open && (
          <>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <DialogTitle>{last?.label ?? open.card.label}</DialogTitle>
                <Mono className="block text-muted">{open.card.metric}</Mono>
              </div>
              <DialogClose asChild>
                <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" data-testid="definition-close">
                  <X size={16} />
                </Button>
              </DialogClose>
            </div>
            {last?.description && <p className="text-sm text-muted">{last.description}</p>}
            {last && (
              <dl className="flex flex-col gap-1.5" data-testid="definition-receipts">
                <Row name="entity">
                  <Pill>{last.entity}</Pill>
                </Row>
                <Row name="entities">{num(last.entities)}</Row>
                {last.window_from && last.window_to && (
                  <Row name="window">
                    {shortDate(last.window_from)} – {shortDate(last.window_to)}
                  </Row>
                )}
                {last.note && <Row name="note">{last.note}</Row>}
                {last.error && <Row name="error">{last.error}</Row>}
              </dl>
            )}
            <a
              href={consoleUrl(`/definitions/metrics?metric=${encodeURIComponent(open.card.metric)}`)}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: 'outline', size: 'sm', className: 'self-start' })}
              data-testid="open-in-console"
            >
              Open in Console
              <ExternalLink size={14} />
            </a>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
