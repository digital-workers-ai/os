import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import { asApiError, getMetricDefinitions, type MetricResponse, type MetricSpec, type Term } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button, buttonVariants } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { consoleUrl } from '@/lib/console'
import { num, shortDate } from '@/lib/format'

const filterText = (filter: Record<string, unknown>) =>
  Object.entries(filter)
    .map(([key, value]) => `${key} = ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(', ')

const termText = (term: Term) =>
  term.filter && Object.keys(term.filter).length > 0 ? `${term.expression} where ${filterText(term.filter)}` : term.expression

const ratioText = (spec: MetricSpec) => (spec.terms ?? []).map(termText).join(` ${spec.op} `)

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h4 className="mb-2 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{title}</h4>
      {children}
    </section>
  )
}

function Row({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 text-sm">
      <dt className="w-24 shrink-0 text-muted">{name}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

export function Definition({ metric, last, onClose }: { metric: string | null; last?: MetricResponse; onClose: () => void }) {
  const defs = useQuery({ queryKey: ['definitions'], queryFn: getMetricDefinitions, enabled: !!metric })
  const spec = metric ? defs.data?.definitions[metric] : undefined
  const provenance = metric ? defs.data?.provenance[metric] : undefined
  const sources = last?.raw_fields ?? provenance?.raw_fields ?? []
  const description = last?.description ?? spec?.description
  const entity = last?.entity ?? spec?.entity
  return (
    <Dialog open={!!metric} onOpenChange={(open) => !open && onClose()}>
      <DialogContent aria-describedby={undefined} data-testid="definition">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <DialogTitle>{last?.label ?? spec?.label ?? metric}</DialogTitle>
            <Mono className="block text-muted">{metric}</Mono>
          </div>
          <DialogClose asChild>
            <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" data-testid="definition-close">
              <X size={16} />
            </Button>
          </DialogClose>
        </div>
        {defs.error ? (
          <ErrorBanner error={asApiError(defs.error)} />
        ) : !defs.data ? (
          <Loading />
        ) : (
          <>
            {description && <p className="text-sm text-muted">{description}</p>}
            <Section title="Definition">
              <dl className="flex flex-col gap-1.5">
                {entity && (
                  <Row name="entity">
                    <Pill>{entity}</Pill>
                  </Row>
                )}
                {spec?.expression && (
                  <Row name="expression">
                    <Mono>{spec.expression}</Mono>
                  </Row>
                )}
                {spec?.terms && (
                  <Row name="ratio">
                    <Mono>{ratioText(spec)}</Mono>
                  </Row>
                )}
                {spec?.filter && Object.keys(spec.filter).length > 0 && (
                  <Row name="filter">
                    <Mono>{filterText(spec.filter)}</Mono>
                  </Row>
                )}
                {spec?.group_by && (
                  <Row name="group by">
                    <Mono>{spec.group_by}</Mono>
                  </Row>
                )}
                {spec?.grain && (
                  <Row name="grain">
                    <Mono>{spec.grain}</Mono>
                  </Row>
                )}
                {spec?.window_attr && (
                  <Row name="window">
                    <Mono>{spec.window_days ? `${spec.window_attr} · ${spec.window_days}d` : spec.window_attr}</Mono>
                  </Row>
                )}
              </dl>
            </Section>
            <Section title="Sources">
              {sources.length > 0 ? (
                <ul className="flex flex-col gap-1" data-testid="definition-sources">
                  {sources.map((field) => (
                    <li key={field}>
                      <Mono>{field}</Mono>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>no raw fields</Empty>
              )}
            </Section>
            <Section title="Receipts">
              {last ? (
                <dl className="flex flex-col gap-1.5" data-testid="definition-receipts">
                  <Row name="entities">{num(last.entities)}</Row>
                  {last.population_size !== undefined && <Row name="population">{num(last.population_size)}</Row>}
                  {last.window_from && last.window_to && (
                    <Row name="window">
                      {shortDate(last.window_from)} – {shortDate(last.window_to)}
                    </Row>
                  )}
                  {last.window_bad_values !== undefined && <Row name="bad dates">{num(last.window_bad_values)}</Row>}
                  {last.mixed_currencies && <Row name="currencies">{last.mixed_currencies.join(', ')}</Row>}
                  {last.note && <Row name="note">{last.note}</Row>}
                  {last.error && <Row name="error">{last.error}</Row>}
                </dl>
              ) : (
                <Empty>not evaluated yet</Empty>
              )}
            </Section>
            <a
              href={consoleUrl(`/definitions/metrics?metric=${encodeURIComponent(metric ?? '')}`)}
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
