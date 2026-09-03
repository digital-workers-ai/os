import { useMemo } from 'react'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { HoverTip, TypeChip, typeColor, useHover } from './shared'

export interface OntologyEntity {
  attrs: Record<string, string>
  identity: string[]
}

export interface OntologyRel {
  rel: string
  from: string
  to: string
  cardinality: string
  grounding: string
}

export interface OntologyResponse {
  source_priority: string[]
  entities: Record<string, OntologyEntity>
  relationships: OntologyRel[]
}

interface Placed {
  type: string
  x: number
  y: number
}

interface CycleNode extends SimulationNodeDatum {
  id: string
}

interface EdgePath {
  rel: OntologyRel
  d: string
  lx: number
  ly: number
}

const NODE_W = 180
const NODE_H = 48
const COL_GAP = 420
const ROW_GAP = 70
const MIN_W = 900
const MIN_H = 320
const MARGIN = 40
const LABEL_T = [0.5, 0.12, 0.3, 0.7, 0.88]

const bezierAt = (t: number, x0: number, y0: number, x1: number, y1: number) => {
  const xm = (x0 + x1) / 2
  const u = 1 - t
  return {
    x: u * u * u * x0 + 3 * u * u * t * xm + 3 * u * t * t * xm + t * t * t * x1,
    y: u * u * u * y0 + 3 * u * u * t * y0 + 3 * u * t * t * y1 + t * t * t * y1,
  }
}

function layerTypes(types: string[], rels: OntologyRel[]) {
  const connected = new Set(rels.flatMap((r) => [r.from, r.to]))
  const nodes = types.filter((t) => connected.has(t))
  const indeg = new Map(nodes.map((n) => [n, 0]))
  for (const r of rels) indeg.set(r.to, (indeg.get(r.to) ?? 0) + 1)
  const depth = new Map<string, number>()
  const queue = nodes.filter((n) => indeg.get(n) === 0)
  for (const n of queue) depth.set(n, 0)
  while (queue.length) {
    const n = queue.shift()!
    for (const r of rels.filter((r) => r.from === n)) {
      depth.set(r.to, Math.max(depth.get(r.to) ?? 0, (depth.get(n) ?? 0) + 1))
      indeg.set(r.to, (indeg.get(r.to) ?? 0) - 1)
      if (indeg.get(r.to) === 0) queue.push(r.to)
    }
  }
  const cyclic = nodes.filter((n) => (indeg.get(n) ?? 0) > 0)
  const unconnected = types.filter((t) => !connected.has(t))
  return { depth, cyclic, unconnected }
}

function buildLayout(types: string[], rels: OntologyRel[]) {
  const { depth, cyclic, unconnected } = layerTypes(types, rels)
  const layered = types.filter((t) => depth.has(t))
  const cols = layered.length ? Math.max(...layered.map((t) => depth.get(t)!)) + 1 : 0
  const columns = Array.from({ length: cols }, (_, d) => layered.filter((t) => depth.get(t) === d))
  const tallest = Math.max(1, ...columns.map((c) => c.length), cyclic.length)
  const vbH = Math.max(MIN_H, tallest * ROW_GAP + 2 * MARGIN)
  const contentW = (cols - 1) * COL_GAP + NODE_W + (cyclic.length ? COL_GAP : 0)
  const vbW = Math.max(MIN_W, contentW + 2 * MARGIN)
  const offsetX = (vbW - contentW) / 2

  const placed = new Map<string, Placed>()
  columns.forEach((col, d) => {
    const colH = col.length * ROW_GAP - (ROW_GAP - NODE_H)
    col.forEach((type, i) => {
      placed.set(type, { type, x: offsetX + d * COL_GAP, y: (vbH - colH) / 2 + i * ROW_GAP })
    })
  })

  if (cyclic.length) {
    const cx = offsetX + cols * COL_GAP + NODE_W / 2
    const simNodes: CycleNode[] = cyclic.map((type) => ({ id: type, x: cx, y: vbH / 2 }))
    const cycleSet = new Set(cyclic)
    const links: SimulationLinkDatum<CycleNode>[] = rels
      .filter((r) => cycleSet.has(r.from) && cycleSet.has(r.to))
      .map((r) => ({ source: r.from, target: r.to }))
    const sim = forceSimulation(simNodes)
      .force('link', forceLink<CycleNode, SimulationLinkDatum<CycleNode>>(links).id((d) => d.id).distance(140))
      .force('charge', forceManyBody().strength(-600))
      .force('center', forceCenter(cx, vbH / 2))
      .force('collide', forceCollide(NODE_W / 2 + 12))
      .stop()
    for (let i = 0; i < 200; i++) sim.tick()
    for (const n of simNodes) placed.set(n.id, { type: n.id, x: (n.x ?? cx) - NODE_W / 2, y: (n.y ?? 0) - NODE_H / 2 })
  }

  const outs = new Map<string, OntologyRel[]>()
  const ins = new Map<string, OntologyRel[]>()
  for (const r of rels) {
    outs.set(r.from, [...(outs.get(r.from) ?? []), r])
    ins.set(r.to, [...(ins.get(r.to) ?? []), r])
  }
  const yOf = (t: string) => placed.get(t)?.y ?? 0
  const port = (list: OntologyRel[], r: OntologyRel, base: number, by: (r: OntologyRel) => string) => {
    const sorted = [...list].sort((a, b) => yOf(by(a)) - yOf(by(b)))
    return base + (NODE_H * (sorted.indexOf(r) + 1)) / (sorted.length + 1)
  }

  const raw = rels.map((r) => {
    const s = placed.get(r.from)!
    const t = placed.get(r.to)!
    const x0 = s.x + NODE_W
    const y0 = port(outs.get(r.from) ?? [], r, s.y, (e) => e.to)
    const x1 = t.x
    const y1 = port(ins.get(r.to) ?? [], r, t.y, (e) => e.from)
    return { r, x0, y0, x1, y1, mid: (y0 + y1) / 2 }
  })

  const taken: { x: number; y: number }[] = []
  const labelSpot = (e: (typeof raw)[number]) => {
    const candidates = LABEL_T.map((t) => bezierAt(t, e.x0, e.y0, e.x1, e.y1))
    const free = candidates.find((p) => !taken.some((q) => Math.abs(q.x - p.x) < 72 && Math.abs(q.y - p.y) < 22))
    const spot = free ?? candidates[0]
    taken.push(spot)
    return spot
  }
  const edges: EdgePath[] = [...raw]
    .sort((a, b) => a.mid - b.mid)
    .map((e) => {
      const xm = (e.x0 + e.x1) / 2
      const p = labelSpot(e)
      return {
        rel: e.r,
        d: `M${e.x0},${e.y0} C${xm},${e.y0} ${xm},${e.y1} ${e.x1},${e.y1}`,
        lx: p.x,
        ly: p.y,
      }
    })

  return { placed: [...placed.values()], edges, cyclic, unconnected, vbW, vbH }
}

export function OntologyGraph({ data }: { data: OntologyResponse }) {
  const types = useMemo(() => Object.keys(data.entities).sort(), [data])
  const layout = useMemo(() => buildLayout(types, data.relationships), [types, data])
  const { rootRef, hover, show, hide } = useHover()

  const describe = (type: string) => {
    const entity = data.entities[type]
    const attrs = Object.keys(entity.attrs).length
    return entity.identity.length ? `${attrs} attrs · identity: ${entity.identity.join(', ')}` : `${attrs} attrs`
  }

  return (
    <div>
      <div ref={rootRef} className="relative overflow-hidden rounded-lg border border-dbb-warm bg-white">
        <svg
          viewBox={`0 0 ${layout.vbW} ${layout.vbH}`}
          className="w-full"
          role="img"
          aria-label={`Ontology of ${types.length} entity types and ${data.relationships.length} relationships`}
          onMouseLeave={hide}
        >
          <defs>
            <marker
              id="ontology-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="#807F74" />
            </marker>
          </defs>
          {layout.edges.map((e, i) => (
            <g
              key={i}
              onMouseMove={(ev) =>
                show(ev, `${e.rel.from} → ${e.rel.to}`, [`${e.rel.rel} · ${e.rel.cardinality}`, e.rel.grounding])
              }
              onMouseLeave={hide}
            >
              <path d={e.d} fill="none" stroke="#807F74" strokeOpacity={0.6} strokeWidth={1.2} markerEnd="url(#ontology-arrow)" />
              <path d={e.d} fill="none" stroke="transparent" strokeWidth={10} />
              <text
                x={e.lx}
                y={e.ly - 3}
                textAnchor="middle"
                fontSize={10}
                fontWeight={500}
                paintOrder="stroke"
                stroke="#FFFFFF"
                strokeWidth={3}
                className="fill-dbb-charcoal"
              >
                {e.rel.rel}
              </text>
              <text
                x={e.lx}
                y={e.ly + 8}
                textAnchor="middle"
                fontSize={9}
                paintOrder="stroke"
                stroke="#FFFFFF"
                strokeWidth={3}
                className="fill-dbb-muted"
              >
                {e.rel.cardinality}
              </text>
            </g>
          ))}
          {layout.placed.map((p) => {
            const identity = data.entities[p.type].identity.length > 0
            return (
              <g
                key={p.type}
                onMouseMove={(ev) =>
                  show(
                    ev,
                    p.type,
                    Object.entries(data.entities[p.type].attrs).map(([k, v]) => `${k}: ${v}`),
                  )
                }
                onMouseLeave={hide}
              >
                <rect
                  x={p.x}
                  y={p.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill="#FFFFFF"
                  stroke={identity ? '#5D8A5D' : '#E0DCC1'}
                  strokeWidth={identity ? 1.5 : 1}
                />
                <circle cx={p.x + 14} cy={p.y + 19} r={4} fill={typeColor(p.type, types)} />
                <text x={p.x + 24} y={p.y + 23} fontSize={12} fontWeight={500} className="fill-dbb-charcoal">
                  {p.type}
                </text>
                <text x={p.x + 24} y={p.y + 38} fontSize={9.5} className="fill-dbb-muted">
                  {describe(p.type)}
                </text>
              </g>
            )
          })}
        </svg>
        <HoverTip hover={hover} width={rootRef.current?.clientWidth ?? layout.vbW} />
      </div>
      {layout.cyclic.length > 0 && (
        <p className="mt-2 text-xs text-dbb-muted">
          {layout.cyclic.join(', ')} form a cycle and are laid out by force instead of by depth.
        </p>
      )}
      {layout.unconnected.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs text-dbb-muted">Unconnected types</span>
          {layout.unconnected.map((t) => (
            <TypeChip key={t} type={t} color={typeColor(t, types)}>
              {Object.keys(data.entities[t].attrs).length} attrs
            </TypeChip>
          ))}
        </div>
      )}
      <h4 className="mb-2 mt-6 text-sm font-medium text-dbb-charcoal">Relationships · {data.relationships.length}</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>From</TableHead>
            <TableHead>Rel</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Cardinality</TableHead>
            <TableHead>Grounding</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.relationships.map((r, i) => (
            <TableRow key={i}>
              <TableCell className="font-mono text-xs text-dbb-charcoal">{r.from}</TableCell>
              <TableCell className="font-mono text-xs">{r.rel}</TableCell>
              <TableCell className="font-mono text-xs text-dbb-charcoal">{r.to}</TableCell>
              <TableCell className="text-xs">{r.cardinality}</TableCell>
              <TableCell className="font-mono text-xs">{r.grounding}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
