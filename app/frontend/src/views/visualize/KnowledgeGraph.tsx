import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type RefObject,
} from 'react'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { Check, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { HoverTip, TypeChip, typeColor, useHover } from './shared'

export interface GraphNode {
  canonical_id: string
  entity_type: string
  anchor: string
  members: number
}

export interface GraphEdge {
  from: string
  to: string
  rel: string
  grounding: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  counts: { nodes: number; edges: number; by_type: Record<string, number> }
}

export interface GraphView {
  typeFilter: string
  showIsolated: boolean
  hidden: Set<string>
  seed: number
}

interface SimNode extends SimulationNodeDatum {
  id: string
  node: GraphNode
  degree: number
  r: number
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  edge: GraphEdge
}

const H = 640
const PAD = 24
const TICKS = 300

const EMPTY_LAYOUT = { nodes: [] as SimNode[], links: [] as SimLink[], ms: 0 }

function useWidth(ref: RefObject<HTMLElement>) {
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])
  return width
}

const degreesOf = (data: GraphResponse) => {
  const degree = new Map<string, number>()
  for (const e of data.edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1)
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1)
  }
  return degree
}

const mulberry32 = (seed: number) => () => {
  seed = (seed + 0x6d2b79f5) | 0
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}

function fitToViewBox(nodes: SimNode[], W: number) {
  if (nodes.length === 0) return
  const xs = nodes.map((n) => n.x ?? 0)
  const ys = nodes.map((n) => n.y ?? 0)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const scale = Math.min(2, (W - 2 * PAD) / Math.max(1, maxX - minX), (H - 2 * PAD) / Math.max(1, maxY - minY))
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  for (const n of nodes) {
    n.x = W / 2 + ((n.x ?? 0) - cx) * scale
    n.y = H / 2 + ((n.y ?? 0) - cy) * scale
  }
}

function runLayout(nodes: GraphNode[], edges: GraphEdge[], degree: Map<string, number>, seed: number, W: number) {
  const started = performance.now()
  const rng = mulberry32(seed)
  const maxMembers = nodes.reduce((m, n) => Math.max(m, n.members), 1)
  const simNodes: SimNode[] = nodes.map((n) => ({
    id: n.canonical_id,
    node: n,
    degree: degree.get(n.canonical_id) ?? 0,
    r: 4 + 6 * ((n.members - 1) / Math.max(1, maxMembers - 1)),
    x: W / 2 + (rng() - 0.5) * W * 0.8,
    y: H / 2 + (rng() - 0.5) * H * 0.8,
  }))
  const links: SimLink[] = edges.map((e) => ({ source: e.from, target: e.to, edge: e }))
  const sim = forceSimulation(simNodes)
    .randomSource(rng)
    .force('link', forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(36))
    .force('charge', forceManyBody().strength(-50))
    .force('center', forceCenter(W / 2, H / 2))
    .force('collide', forceCollide<SimNode>((d) => d.r + 3))
    .stop()
  for (let i = 0; i < TICKS; i++) sim.tick()
  fitToViewBox(simNodes, W)
  return { nodes: simNodes, links, ms: Math.round(performance.now() - started) }
}

const shortLabel = (anchor: string) => (anchor.length > 28 ? `${anchor.slice(0, 27)}…` : anchor)

export function GraphControls({
  data,
  view,
  onChange,
}: {
  data: GraphResponse
  view: GraphView
  onChange: (view: GraphView) => void
}) {
  const types = useMemo(() => Object.keys(data.counts.by_type).sort(), [data])
  const isolated = useMemo(() => {
    const degree = degreesOf(data)
    return data.nodes.filter((n) => !degree.has(n.canonical_id)).length
  }, [data])
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={view.typeFilter} onValueChange={(typeFilter) => onChange({ ...view, typeFilter })}>
        <SelectTrigger className="h-8 w-[190px] text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All types · {data.counts.nodes}</SelectItem>
          {types.map((t) => (
            <SelectItem key={t} value={t}>
              {t} · {data.counts.by_type[t]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <button
        type="button"
        onClick={() => onChange({ ...view, showIsolated: !view.showIsolated })}
        className={`h-8 rounded-full border px-3 text-xs transition-colors ${
          view.showIsolated
            ? 'border-dbb-charcoal bg-dbb-charcoal text-white'
            : 'border-dbb-warm bg-white text-dbb-muted hover:bg-dbb-sand'
        }`}
      >
        Isolated · {isolated}
      </button>
      <Button variant="outline" size="sm" onClick={() => onChange({ ...view, seed: view.seed + 1 })}>
        Re-layout
      </Button>
    </div>
  )
}

function CopyId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(id)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <div className="flex items-center gap-1">
      <code className="min-w-0 flex-1 break-all font-mono text-[11px] text-dbb-muted">{id}</code>
      <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={copy} aria-label="copy id">
        {copied ? <Check /> : <Copy />}
      </Button>
    </div>
  )
}

function NodePanel({
  node,
  degree,
  edges,
  byId,
  types,
  onSelect,
}: {
  node: GraphNode
  degree: number
  edges: GraphEdge[]
  byId: Map<string, GraphNode>
  types: string[]
  onSelect: (id: string) => void
}) {
  return (
    <div className="space-y-3">
      <div className="break-all text-sm font-medium text-dbb-charcoal">{node.anchor}</div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-dbb-muted">
        <TypeChip type={node.entity_type} color={typeColor(node.entity_type, types)} />
        <span>
          {node.members} members · degree {degree}
        </span>
      </div>
      <CopyId id={node.canonical_id} />
      <div className="text-xs font-medium text-dbb-charcoal">Edges · {edges.length}</div>
      {edges.length === 0 ? (
        <p className="text-xs text-dbb-muted">No edges.</p>
      ) : (
        <ul className="divide-y divide-dbb-warm/40">
          {edges.map((e, i) => {
            const out = e.from === node.canonical_id
            const otherId = out ? e.to : e.from
            const other = byId.get(otherId)
            return (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onSelect(otherId)}
                  className="flex w-full flex-col items-start gap-0.5 py-1.5 text-left hover:bg-dbb-sand"
                >
                  <span className="font-mono text-[11px] text-dbb-muted">
                    {out ? '→' : '←'} {e.rel} · {e.grounding}
                  </span>
                  <span className="break-all text-xs text-dbb-charcoal">{other?.anchor ?? otherId}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export function KnowledgeGraph({
  data,
  view,
  onChange,
}: {
  data: GraphResponse
  view: GraphView
  onChange: (view: GraphView) => void
}) {
  const types = useMemo(() => Object.keys(data.counts.by_type).sort(), [data])
  const degree = useMemo(() => degreesOf(data), [data])
  const byId = useMemo(() => new Map(data.nodes.map((n) => [n.canonical_id, n])), [data])

  const scoped = useMemo(
    () =>
      data.nodes.filter(
        (n) =>
          (view.typeFilter === 'all' || n.entity_type === view.typeFilter) && !view.hidden.has(n.entity_type),
      ),
    [data, view.typeFilter, view.hidden],
  )
  const isolatedCount = useMemo(() => scoped.filter((n) => !degree.has(n.canonical_id)).length, [scoped, degree])

  const { rootRef, hover, show, hide } = useHover()
  const width = useWidth(rootRef)

  const laid = useMemo(() => {
    if (width === 0) return EMPTY_LAYOUT
    const visible = view.showIsolated ? scoped : scoped.filter((n) => degree.has(n.canonical_id))
    const ids = new Set(visible.map((n) => n.canonical_id))
    const edges = data.edges.filter((e) => ids.has(e.from) && ids.has(e.to))
    return runLayout(visible, edges, degree, view.seed, width)
  }, [data, scoped, degree, view.showIsolated, view.seed, width])

  const scopedTypes = useMemo(() => new Set(scoped.map((n) => n.entity_type)), [scoped])
  const labelAll = laid.nodes.length <= 40

  const [selected, setSelected] = useState<string | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0, k: 1 })
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; y: number; px: number; py: number; moved: boolean } | null>(null)
  const dragged = useRef(false)

  useEffect(() => {
    setPan({ x: 0, y: 0, k: 1 })
    hide()
  }, [laid])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const ctm = svg.getScreenCTM()
      if (!ctm) return
      const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse())
      const f = Math.exp(-e.deltaY * 0.002)
      setPan((v) => {
        const k = Math.min(8, Math.max(0.3, v.k * f))
        return { k, x: p.x - ((p.x - v.x) * k) / v.k, y: p.y - ((p.y - v.y) * k) / v.k }
      })
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [])

  const onMouseDown = (e: ReactMouseEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y, moved: false }
  }
  const onMouseMove = (e: ReactMouseEvent) => {
    const d = drag.current
    if (!d) return
    const scale = svgRef.current?.getScreenCTM()?.a ?? 1
    const dx = (e.clientX - d.x) / scale
    const dy = (e.clientY - d.y) / scale
    if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true
    setPan((v) => ({ ...v, x: d.px + dx, y: d.py + dy }))
  }
  const onMouseUp = () => {
    dragged.current = drag.current?.moved ?? false
    drag.current = null
  }

  const toggleType = (t: string) => {
    const hidden = new Set(view.hidden)
    if (hidden.has(t)) hidden.delete(t)
    else hidden.add(t)
    onChange({ ...view, hidden })
  }

  const selectedNode = selected ? byId.get(selected) : undefined
  const selectedEdges = useMemo(
    () => (selected ? data.edges.filter((e) => e.from === selected || e.to === selected) : []),
    [data, selected],
  )

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="min-w-0 flex-1">
        <p className="mb-2 text-xs text-dbb-muted">
          {scoped.length} nodes · {laid.links.length} edges · {scopedTypes.size} types · {isolatedCount} isolated{' '}
          {view.showIsolated ? 'shown' : 'hidden'} · layout {laid.ms}ms
        </p>
        <div ref={rootRef} className="relative overflow-hidden rounded-lg border border-dbb-warm bg-white">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${width || 1} ${H}`}
            className="h-[640px] w-full cursor-grab select-none active:cursor-grabbing"
            role="img"
            aria-label={`Knowledge graph of ${scoped.length} entities`}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={() => {
              onMouseUp()
              hide()
            }}
          >
            <g transform={`translate(${pan.x} ${pan.y}) scale(${pan.k})`}>
              {laid.links.map((l, i) => {
                const s = l.source as SimNode
                const t = l.target as SimNode
                const lit = selected !== null && (s.id === selected || t.id === selected)
                return (
                  <g
                    key={i}
                    onMouseMove={(e) =>
                      show(e, l.edge.rel, [`${s.node.anchor} → ${t.node.anchor}`, l.edge.grounding])
                    }
                    onMouseLeave={hide}
                  >
                    <line
                      x1={s.x}
                      y1={s.y}
                      x2={t.x}
                      y2={t.y}
                      stroke={lit ? '#1A1A1A' : '#E0DCC1'}
                      strokeOpacity={0.8}
                      strokeWidth={lit ? 1.5 : 1}
                    />
                    <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="transparent" strokeWidth={8} />
                  </g>
                )
              })}
              {laid.nodes.map((n) => (
                <g key={n.id}>
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={n.r}
                    fill={typeColor(n.node.entity_type, types)}
                    stroke={selected === n.id ? '#1A1A1A' : '#FFFFFF'}
                    strokeWidth={selected === n.id ? 2 : 1}
                    className="cursor-pointer"
                    onMouseMove={(e) =>
                      show(e, n.node.anchor, [n.node.entity_type, `${n.node.members} members · degree ${n.degree}`])
                    }
                    onMouseLeave={hide}
                    onClick={() => {
                      if (!dragged.current) setSelected(n.id)
                    }}
                  />
                  {(labelAll || n.degree >= 2) && (
                    <text
                      x={(n.x ?? 0) + n.r + 3}
                      y={(n.y ?? 0) + 3}
                      className="pointer-events-none fill-dbb-charcoal text-[10px]"
                    >
                      {shortLabel(n.node.anchor)}
                    </text>
                  )}
                </g>
              ))}
            </g>
          </svg>
          <HoverTip hover={hover} width={width} />
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {types.map((t) => (
            <TypeChip
              key={t}
              type={t}
              color={typeColor(t, types)}
              active={!view.hidden.has(t) && (view.typeFilter === 'all' || view.typeFilter === t)}
              onClick={() => toggleType(t)}
            >
              {data.counts.by_type[t]}
            </TypeChip>
          ))}
        </div>
      </div>
      <aside className="shrink-0 rounded-lg border border-dbb-warm bg-dbb-surface p-4 lg:w-[320px]">
        {selectedNode ? (
          <NodePanel
            node={selectedNode}
            degree={degree.get(selectedNode.canonical_id) ?? 0}
            edges={selectedEdges}
            byId={byId}
            types={types}
            onSelect={setSelected}
          />
        ) : (
          <p className="text-xs text-dbb-muted">Click a node to see its edges. Drag to pan, wheel to zoom.</p>
        )}
      </aside>
    </div>
  )
}
