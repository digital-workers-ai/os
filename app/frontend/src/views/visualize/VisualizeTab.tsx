import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { asApiError, get } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { FilterChip } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { anchorText, num } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Canvas, displayLabel, hubsOf, scopeGraph, type GraphResponse } from './KnowledgeGraph'
import { TypeChip, typeColor } from './shared'

const HUBS = [
  ['company', 'Company'],
  ['person', 'Person'],
] as const

type HubType = (typeof HUBS)[number][0]

const MONO = 'font-mono text-xs'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const ROW = 'cursor-pointer hover:bg-dbb-sand/50'
const SPLIT_FILL = 'grid items-start gap-6 lg:grid-cols-[0.8fr_1.4fr] lg:grid-rows-[minmax(0,1fr)] lg:h-full'
const FILL = 'min-w-0 lg:flex lg:flex-col lg:h-full'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'
const CANVAS = 'flex flex-col lg:min-h-0 lg:flex-1'

const labelText = (label: string, anchor: string) => (label === anchor ? anchorText(anchor) : label)

function Graph({ data }: { data: GraphResponse }) {
  const scope = useMemo(() => scopeGraph(data), [data])
  const lists = useMemo(() => new Map(HUBS.map(([t]) => [t, hubsOf(scope, t)])), [scope])
  const hubs = useMemo(() => new Map([...lists.values()].flat().map((c) => [c.hub.canonical_id, c])), [lists])
  const [type, setType] = useState<HubType>('company')
  const [selected, setSelected] = useState<string | null>(null)
  const [focus, setFocus] = useState<string | null>(null)
  const rows = lists.get(type)!
  const focusSun = focus ? (hubs.get(focus) ?? null) : null
  const shown = useMemo(() => (focusSun ? [focusSun] : rows.filter((c) => c.edges.length > 0)), [rows, focusSun])
  const legend = useMemo(() => {
    const counts = new Map<string, number>()
    for (const c of shown) for (const n of c.nodes) counts.set(n.entity_type, (counts.get(n.entity_type) ?? 0) + 1)
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [shown])
  const rowRef = useRef<HTMLTableRowElement>(null)
  useEffect(() => {
    rowRef.current?.scrollIntoView({ block: 'nearest' })
  }, [focus])

  const clear = () => {
    setFocus(null)
    setSelected(null)
  }
  const pickType = (t: HubType) => {
    setType(t)
    clear()
  }
  const select = (id: string) => {
    setSelected(id)
    const hub = hubs.get(id)
    if (!hub) return
    setFocus(id)
    setType(hub.hub.entity_type as HubType)
  }
  const pick = (id: string) => (id === focus ? clear() : select(id))

  const node = selected ? scope.byId.get(selected) : undefined
  const edges = selected ? (scope.edgesOf.get(selected) ?? []) : []
  const title = HUBS.find(([t]) => t === type)![1]

  return (
    <div className={SPLIT_FILL}>
      <SectionCard
        title={
          <div className="flex gap-1.5">
            {HUBS.map(([t]) => (
              <FilterChip key={t} on={t === type} onClick={() => pickType(t)} data-testid={`visualize-toggle-${t}`}>
                {t} {num(lists.get(t)!.length)}
              </FilterChip>
            ))}
          </div>
        }
        className={FILL}
        bodyClassName={BODY}
        testId="visualize"
      >
        <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="visualize-table">
          <TableHeader className={STICKY_HEAD}>
            <TableRow>
              <TableHead hint="Drawn as a sun with the things linked to it">
                {title} ({num(rows.length)})
              </TableHead>
              <TableHead hint="How many things connect to it" className={cn(NUM, 'w-20')}>Links</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => {
              const id = c.hub.canonical_id
              const on = id === focus
              return (
                <TableRow
                  key={id}
                  ref={on ? rowRef : undefined}
                  className={ROW}
                  data-testid="visualize-row"
                  data-state={on ? 'selected' : undefined}
                  aria-selected={on}
                  onClick={() => pick(id)}
                >
                  <TableCell className={KEY}>
                    {labelText(c.hub.label, c.hub.anchor)}
                    {c.hub.label !== c.hub.anchor ? <span className={cn(MONO, 'block font-normal text-dbb-muted')}>{anchorText(c.hub.anchor)}</span> : null}
                  </TableCell>
                  <TableCell className={NUM}>{num(c.edges.length)}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </SectionCard>
      <SectionCard className={FILL} bodyClassName={CANVAS}>
        <Canvas scope={scope} clusters={shown} focused={!!focusSun} selected={selected} onSelect={select} />
        <div className="mt-3 flex shrink-0 flex-wrap gap-1.5" data-testid="visualize-legend">
          {legend.map(([t, n]) => (
            <TypeChip key={t} type={t} color={typeColor(t, scope.types)}>
              {num(n)}
            </TypeChip>
          ))}
        </div>
        <div className="mt-2 flex h-7 shrink-0 items-center gap-1.5 overflow-x-auto text-xs" data-testid="visualize-selected">
          {node && (
            <>
              <span className={cn(KEY, 'whitespace-nowrap')}>{displayLabel(node)}</span>
              <TypeChip type={node.entity_type} color={typeColor(node.entity_type, scope.types)} />
              {edges.map((e, i) => {
                const otherId = e.from === selected ? e.to : e.from
                const other = scope.byId.get(otherId)!
                return (
                  <TypeChip key={i} type={e.rel} color={typeColor(other.entity_type, scope.types)} onClick={() => select(otherId)}>
                    → {displayLabel(other)}
                  </TypeChip>
                )
              })}
            </>
          )}
        </div>
      </SectionCard>
    </div>
  )
}

export function VisualizeTab() {
  const graph = useQuery({ queryKey: ['graph'], queryFn: () => get<GraphResponse>('/api/graph') })
  if (graph.data) return <Graph data={graph.data} />
  if (graph.error) return <ErrorBanner error={asApiError(graph.error)} />
  return <Loading />
}
