import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import {
  asApiError,
  getMetricDefinitions,
  type Filter,
  type MetricCardSpec,
  type MetricResponse,
  type MetricSpec,
  type TableCardSpec,
  type Term,
  type TopResponse,
} from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button, buttonVariants } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { consoleUrl } from '@/lib/console'
import { num, shortDate } from '@/lib/format'

export type Opened = { metric: MetricCardSpec; last?: MetricResponse } | { table: TableCardSpec; last?: TopResponse; filter: Filter }

const filterText = (filter: Record<string, unknown>) =>
  Object.entries(filter)
    .map(([key, value]) => `${key} = ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(', ')

const termText = (term: Term) =>
  term.filter && Object.keys(term.filter).length > 0 ? `${term.expression} where ${filterText(term.filter)}` : term.expression

const ratioText = (spec: MetricSpec) => (spec.terms ?? []).map(termText).join(` ${spec.op} `)

const some = (filter?: Record<string, unknown>): filter is Record<string, unknown> => !!filter && Object.keys(filter).length > 0

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

function Header({ title, name }: { title: string; name: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <DialogTitle>{title}</DialogTitle>
        <Mono className="block text-muted">{name}</Mono>
      </div>
      <DialogClose asChild>
        <Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8 text-muted" aria-label="close" data-testid="definition-close">
          <X size={16} />
        </Button>
      </DialogClose>
    </div>
  )
}

function Window({ from, to }: { from?: string; to?: string }) {
  if (!from || !to) return null
  return (
    <Row name="window">
      {shortDate(from)} – {shortDate(to)}
    </Row>
  )
}

function ConsoleLink({ path }: { path: string }) {
  return (
    <a
      href={consoleUrl(path)}
      target="_blank"
      rel="noreferrer"
      className={buttonVariants({ variant: 'outline', size: 'sm', className: 'self-start' })}
      data-testid="open-in-console"
    >
      Open in Console
      <ExternalLink size={14} />
    </a>
  )
}

function MetricDetails({ card, last }: { card: MetricCardSpec; last?: MetricResponse }) {
  const defs = useQuery({ queryKey: ['definitions'], queryFn: getMetricDefinitions })
  const spec = defs.data?.definitions[card.metric]
  const provenance = defs.data?.provenance[card.metric]
  const sources = last?.raw_fields ?? provenance?.raw_fields ?? []
  const description = last?.description ?? spec?.description
  const entity = last?.entity ?? spec?.entity
  return (
    <>
      <Header title={last?.label ?? spec?.label ?? card.metric} name={card.metric} />
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
              {some(spec?.filter) && (
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
                <Window from={last.window_from} to={last.window_to} />
                {last.window_bad_values !== undefined && <Row name="bad dates">{num(last.window_bad_values)}</Row>}
                {some(last.applied_filter) && (
                  <Row name="filter">
                    <Mono>{filterText(last.applied_filter)}</Mono>
                  </Row>
                )}
                {last.mixed_currencies && <Row name="currencies">{last.mixed_currencies.join(', ')}</Row>}
                {last.note && <Row name="note">{last.note}</Row>}
                {last.error && <Row name="error">{last.error}</Row>}
              </dl>
            ) : (
              <Empty>not evaluated yet</Empty>
            )}
          </Section>
          <ConsoleLink path={`/definitions/metrics?metric=${encodeURIComponent(card.metric)}`} />
        </>
      )}
    </>
  )
}

function TableDetails({ card, last, filter }: { card: TableCardSpec; last?: TopResponse; filter: Filter }) {
  return (
    <>
      <Header title={card.label} name={`${card.entity} by ${card.rank}`} />
      <Section title="Definition">
        <dl className="flex flex-col gap-1.5">
          <Row name="entity">
            <Pill>{card.entity}</Pill>
          </Row>
          <Row name="rank">
            <Mono>{`${card.rank} · top ${num(card.limit)}`}</Mono>
          </Row>
          <Row name="columns">
            <Mono>{card.columns.map((column) => `${column.attr} · ${column.type}`).join(', ')}</Mono>
          </Row>
          {card.window_attr && (
            <Row name="window">
              <Mono>{card.window_attr}</Mono>
            </Row>
          )}
          {some(filter) && (
            <Row name="filter">
              <Mono>{filterText(filter)}</Mono>
            </Row>
          )}
        </dl>
      </Section>
      <Section title="Receipts">
        {last ? (
          <dl className="flex flex-col gap-1.5" data-testid="definition-receipts">
            <Row name="entities">{num(last.entities)}</Row>
            <Row name="rows">{num(last.rows.length)}</Row>
            <Window from={last.window_from} to={last.window_to} />
          </dl>
        ) : (
          <Empty>not evaluated yet</Empty>
        )}
      </Section>
      <ConsoleLink path="/definitions/dashboards" />
    </>
  )
}

export function Definition({ open, onClose }: { open: Opened | null; onClose: () => void }) {
  return (
    <Dialog open={!!open} onOpenChange={(shown) => !shown && onClose()}>
      <DialogContent aria-describedby={undefined} data-testid="definition">
        {open && ('table' in open ? <TableDetails card={open.table} last={open.last} filter={open.filter} /> : <MetricDetails card={open.metric} last={open.last} />)}
      </DialogContent>
    </Dialog>
  )
}
