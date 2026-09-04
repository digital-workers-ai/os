import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type RefObject,
} from 'react'
import { Check, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { anchorText, plural } from '@/lib/format'
import { HoverTip, TypeChip, typeColor, useHover } from './shared'

export interface GraphNode {
  canonical_id: string
  entity_type: string
  anchor: string
  label: string
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
  hidden: Set<string>
  focus: string | null
}

export interface Cluster {
  hub: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphScope {
  types: string[]
  degree: Map<string, number>
  clusters: Cluster[]
  unlinked: GraphNode[]
  edgeCount: number
}

const RING_STEP = 56
const FOCUS_RING_STEP = 110
const ARC_SPACING = 22
const LABEL_ALL_MAX = 12
const LABEL_CHARS = 22
const SUN_PAD = 10
const GUTTER = 20
const HUB_PRIORITY: Record<string, number> = { company: 2, person: 1 }

export const displayLabel = (n: GraphNode) =>
  n.label === n.anchor ? n.anchor.slice(n.anchor.lastIndexOf('|') + 1) : n.label

const truncate = (s: string) => (s.length > LABEL_CHARS ? `${s.slice(0, LABEL_CHARS - 1)}…` : s)

const adjacency = (edges: GraphEdge[]) => {
  const adj = new Map<string, Set<string>>()
  const link = (a: string, b: string) => {
    if (!adj.has(a)) adj.set(a, new Set())
    adj.get(a)!.add(b)
  }
  for (const e of edges) {
    link(e.from, e.to)
    link(e.to, e.from)
  }
  return adj
}

function pickHub(nodes: GraphNode[], degree: Map<string, number>) {
  const rank = (n: GraphNode) => [HUB_PRIORITY[n.entity_type] ?? 0, degree.get(n.canonical_id) ?? 0]
  return nodes.reduce((best, n) => {
    const [bp, bd] = rank(best)
    const [np, nd] = rank(n)
    if (np !== bp) return np > bp ? n : best
    if (nd !== bd) return nd > bd ? n : best
    return displayLabel(n) < displayLabel(best) ? n : best
  })
}

export function scopeGraph(data: GraphResponse, view: Pick<GraphView, 'typeFilter' | 'hidden'>): GraphScope {
  const types = Object.keys(data.counts.by_type).sort()
  const lens = new Set<string>()
  if (view.typeFilter !== 'all') {
    const fullAdj = adjacency(data.edges)
    for (const n of data.nodes) {
      if (n.entity_type !== view.typeFilter) continue
      lens.add(n.canonical_id)
      for (const m of fullAdj.get(n.canonical_id) ?? []) lens.add(m)
    }
  }
  const nodes = data.nodes.filter(
    (n) => (view.typeFilter === 'all' || lens.has(n.canonical_id)) && !view.hidden.has(n.entity_type),
  )
  const byId = new Map(nodes.map((n) => [n.canonical_id, n]))
  const edges = data.edges.filter((e) => byId.has(e.from) && byId.has(e.to))
  const degree = new Map<string, number>()
  for (const e of edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1)
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1)
  }
  const adj = adjacency(edges)
  const seen = new Set<string>()
  const clusters: Cluster[] = []
  for (const start of nodes) {
    if (seen.has(start.canonical_id) || !adj.has(start.canonical_id)) continue
    const found: GraphNode[] = []
    const queue = [start.canonical_id]
    seen.add(start.canonical_id)
    while (queue.length) {
      const id = queue.shift()!
      found.push(byId.get(id)!)
      for (const m of adj.get(id) ?? []) {
        if (seen.has(m)) continue
        seen.add(m)
        queue.push(m)
      }
    }
    const ids = new Set(found.map((n) => n.canonical_id))
    clusters.push({ hub: pickHub(found, degree), nodes: found, edges: edges.filter((e) => ids.has(e.from)) })
  }
  clusters.sort(
    (a, b) => b.nodes.length - a.nodes.length || displayLabel(a.hub).localeCompare(displayLabel(b.hub)),
  )
  return { types, degree, clusters, unlinked: nodes.filter((n) => !degree.has(n.canonical_id)), edgeCount: edges.length }
}

export const graphSummary = (scope: GraphScope) => {
  const linked = scope.clusters.reduce((n, c) => n + c.nodes.length, 0)
  return `${plural(scope.clusters.length, 'cluster')} · ${linked} linked nodes · ${scope.unlinked.length} unlinked · ${plural(scope.edgeCount, 'edge')}`
}

type Anchor = 'start' | 'end' | 'middle'

interface Box {
  x0: number
  y0: number
  x1: number
  y1: number
}

interface Spot {
  x: number
  y: number
  anchor: Anchor
}

interface Dot {
  node: GraphNode
  x: number
  y: number
  r: number
  angle: number
  depth: number
  degree: number
  branch: boolean
}

interface Link {
  a: Dot
  b: Dot
  edge: GraphEdge
}

interface Label extends Spot {
  id: string
  text: string
  strong: boolean
}

interface Sun {
  hub: GraphNode
  heading: string
  radius: number
  dots: Dot[]
  links: Link[]
  labels: Label[]
  bounds: Box
}

interface PlacedSun {
  sun: Sun
  ox: number
  oy: number
}

const textBox = (spot: Spot, text: string, px: number): Box => {
  const w = text.length * px * 0.6 + 2
  const x0 = spot.anchor === 'start' ? spot.x : spot.anchor === 'end' ? spot.x - w : spot.x - w / 2
  return { x0, y0: spot.y - px * 0.8, x1: x0 + w, y1: spot.y + px * 0.25 }
}

const boxesHit = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1

const circleHits = (box: Box, dot: Dot) => {
  const dx = dot.x - Math.min(Math.max(dot.x, box.x0), box.x1)
  const dy = dot.y - Math.min(Math.max(dot.y, box.y0), box.y1)
  return dx * dx + dy * dy < dot.r * dot.r
}

const grow = (box: Box, other: Box) => {
  box.x0 = Math.min(box.x0, other.x0)
  box.y0 = Math.min(box.y0, other.y0)
  box.x1 = Math.max(box.x1, other.x1)
  box.y1 = Math.max(box.y1, other.y1)
}

function layoutSun(cluster: Cluster, degree: Map<string, number>, maxMembers: number, step: number, labelDepth: number): Sun {
  const byId = new Map(cluster.nodes.map((n) => [n.canonical_id, n]))
  const adj = adjacency(cluster.edges)
  const hubId = cluster.hub.canonical_id
  const byTypeThenLabel = (a: string, b: string) => {
    const na = byId.get(a)!
    const nb = byId.get(b)!
    return na.entity_type.localeCompare(nb.entity_type) || displayLabel(na).localeCompare(displayLabel(nb))
  }
  const depth = new Map([[hubId, 0]])
  const children = new Map<string, string[]>()
  const queue = [hubId]
  while (queue.length) {
    const id = queue.shift()!
    const kids = [...(adj.get(id) ?? [])].filter((m) => !depth.has(m)).sort(byTypeThenLabel)
    children.set(id, kids)
    for (const k of kids) {
      depth.set(k, depth.get(id)! + 1)
      queue.push(k)
    }
  }
  const leaves = new Map<string, number>()
  const countLeaves = (id: string): number => {
    const kids = children.get(id)!
    const n = kids.length ? kids.reduce((sum, k) => sum + countLeaves(k), 0) : 1
    leaves.set(id, n)
    return n
  }
  const totalLeaves = countLeaves(hubId)
  const angle = new Map<string, number>()
  const assignSector = (id: string, a0: number, a1: number) => {
    angle.set(id, (a0 + a1) / 2)
    let a = a0
    for (const k of children.get(id)!) {
      const span = ((a1 - a0) * leaves.get(k)!) / leaves.get(id)!
      assignSector(k, a, a + span)
      a += span
    }
  }
  assignSector(hubId, -Math.PI / 2, 1.5 * Math.PI)
  const maxDepth = Math.max(...depth.values())
  const ring = [0, Math.max(step, (totalLeaves * ARC_SPACING) / (2 * Math.PI))]
  for (let d = 2; d <= maxDepth; d++) ring.push(ring[d - 1] + step)
  const dots: Dot[] = cluster.nodes.map((node) => {
    const id = node.canonical_id
    const d = depth.get(id)!
    const a = angle.get(id)!
    return {
      node,
      x: ring[d] * Math.cos(a),
      y: ring[d] * Math.sin(a),
      r: 5 + (6 * (node.members - 1)) / Math.max(1, maxMembers - 1),
      angle: a,
      depth: d,
      degree: degree.get(id) ?? 0,
      branch: children.get(id)!.length > 0,
    }
  })
  const dotById = new Map(dots.map((d) => [d.node.canonical_id, d]))
  const links = cluster.edges.map((edge) => ({ a: dotById.get(edge.from)!, b: dotById.get(edge.to)!, edge }))
  const radius = ring[maxDepth] + Math.max(...dots.map((d) => d.r)) + 8
  const heading = truncate(displayLabel(cluster.hub))
  const headingBox = textBox({ x: 0, y: -radius - 8, anchor: 'middle' }, heading, 11)
  const taken: Box[] = [headingBox]
  const labels: Label[] = []
  const wanted = dots
    .filter((d) => d.depth > 0 && (d.branch || d.depth <= labelDepth))
    .sort((a, b) => Number(b.branch) - Number(a.branch) || a.depth - b.depth)
  for (const d of wanted) {
    const text = truncate(displayLabel(d.node))
    const sx = Math.cos(d.angle) >= 0 ? 1 : -1
    const sy = Math.sin(d.angle) >= 0 ? 1 : -1
    const anchorOf = (s: number): Anchor => (s > 0 ? 'start' : 'end')
    const side = (s: number): Spot => ({ x: d.x + s * (d.r + 4), y: d.y + 3.5, anchor: anchorOf(s) })
    const vertical = (s: number): Spot => ({ x: d.x, y: s > 0 ? d.y + d.r + 11 : d.y - d.r - 5, anchor: 'middle' })
    const diagonal = (h: number, v: number): Spot => ({
      x: d.x + h * (d.r + 2),
      y: v > 0 ? d.y + d.r + 9 : d.y - d.r - 3,
      anchor: anchorOf(h),
    })
    const spots = [
      side(sx),
      vertical(sy),
      diagonal(sx, sy),
      diagonal(sx, -sy),
      vertical(-sy),
      diagonal(-sx, sy),
      diagonal(-sx, -sy),
      side(-sx),
    ]
    for (const spot of spots) {
      const box = textBox(spot, text, 10)
      if (taken.some((t) => boxesHit(box, t)) || dots.some((o) => circleHits(box, o))) continue
      taken.push(box)
      labels.push({ id: d.node.canonical_id, text, strong: d.branch, ...spot })
      break
    }
  }
  const bounds: Box = { x0: -radius, y0: headingBox.y0, x1: radius, y1: radius }
  for (const t of taken) grow(bounds, t)
  bounds.x0 -= SUN_PAD
  bounds.y0 -= SUN_PAD
  bounds.x1 += SUN_PAD
  bounds.y1 += SUN_PAD
  return { hub: cluster.hub, heading, radius, dots, links, labels, bounds }
}

interface Shelf {
  x: number
  w: number
  y: number
}

function raise(skyline: Shelf[], x: number, right: number, top: number) {
  const next: Shelf[] = []
  for (const s of skyline) {
    const end = s.x + s.w
    if (end <= x || s.x >= right) {
      next.push(s)
      continue
    }
    if (s.x < x) next.push({ x: s.x, w: x - s.x, y: s.y })
    if (end > right) next.push({ x: right, w: end - right, y: s.y })
  }
  next.push({ x, w: right - x, y: top })
  return next.sort((a, b) => a.x - b.x)
}

function tile(suns: Sun[], width: number) {
  const placed: PlacedSun[] = []
  const pending = [...suns]
  let skyline: Shelf[] = [{ x: 0, w: width, y: 0 }]
  let height = 0
  while (pending.length) {
    let i = 0
    for (let j = 1; j < skyline.length; j++) if (skyline[j].y < skyline[i].y) i = j
    const { x, y } = skyline[i]
    let end = i
    let room = 0
    while (end < skyline.length && skyline[end].y <= y) room += skyline[end++].w
    room = Math.min(room, width - x)
    const k = pending.findIndex((s) => s.bounds.x1 - s.bounds.x0 <= room)
    if (k < 0 && (x > 0 || room < width)) {
      skyline = raise(skyline, x, x + room, Math.min(skyline[i - 1]?.y ?? Infinity, skyline[end]?.y ?? Infinity))
      continue
    }
    const [sun] = pending.splice(Math.max(k, 0), 1)
    const w = sun.bounds.x1 - sun.bounds.x0
    const h = sun.bounds.y1 - sun.bounds.y0
    placed.push({ sun, ox: x - sun.bounds.x0, oy: y - sun.bounds.y0 })
    skyline = raise(skyline, x, Math.min(width, x + w + GUTTER), y + h + GUTTER)
    height = Math.max(height, y + h)
  }
  return { suns: placed, height }
}

const EMPTY_LAYOUT = { suns: [] as PlacedSun[], height: 0 }

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

export function GraphControls({
  counts,
  scope,
  view,
  onChange,
}: {
  counts: GraphResponse['counts']
  scope: GraphScope
  view: GraphView
  onChange: (view: GraphView) => void
}) {
  const hubs = useMemo(
    () => [...scope.clusters].sort((a, b) => displayLabel(a.hub).localeCompare(displayLabel(b.hub))),
    [scope],
  )
  const focus = hubs.some((c) => c.hub.canonical_id === view.focus) ? view.focus! : 'all'
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={focus} onValueChange={(v) => onChange({ ...view, focus: v === 'all' ? null : v })}>
        <SelectTrigger className="h-8 w-[210px] text-xs" aria-label="focus cluster">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All clusters · {scope.clusters.length}</SelectItem>
          {hubs.map((c) => (
            <SelectItem key={c.hub.canonical_id} value={c.hub.canonical_id}>
              {displayLabel(c.hub)} · {c.nodes.length}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={view.typeFilter} onValueChange={(typeFilter) => onChange({ ...view, typeFilter })}>
        <SelectTrigger className="h-8 w-[190px] text-xs" aria-label="type filter">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All types · {counts.nodes}</SelectItem>
          {scope.types.map((t) => (
            <SelectItem key={t} value={t}>
              {t} · {counts.by_type[t]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
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
  hubs,
  types,
  onSelect,
  onFocus,
}: {
  node: GraphNode
  degree: number
  edges: GraphEdge[]
  byId: Map<string, GraphNode>
  hubs: Set<string>
  types: string[]
  onSelect: (id: string) => void
  onFocus: (id: string) => void
}) {
  return (
    <div className="space-y-3">
      <div className="break-words text-sm font-medium text-dbb-charcoal">{displayLabel(node)}</div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-dbb-muted">
        <TypeChip type={node.entity_type} color={typeColor(node.entity_type, types)} />
        <span>
          {node.members} members · degree {degree}
        </span>
      </div>
      <div className="break-all font-mono text-[11px] text-dbb-muted">{anchorText(node.anchor)}</div>
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
                  onClick={() => (hubs.has(otherId) ? onFocus(otherId) : onSelect(otherId))}
                  className="flex w-full flex-col items-start gap-0.5 py-1.5 text-left hover:bg-dbb-sand"
                >
                  <span className="font-mono text-[11px] text-dbb-muted">
                    {out ? '→' : '←'} {e.rel} · {e.grounding}
                  </span>
                  <span className="break-words text-xs text-dbb-charcoal">
                    {other ? displayLabel(other) : otherId}
                    {other && hubs.has(otherId) && <span className="ml-1 text-dbb-muted">· cluster hub</span>}
                  </span>
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
  scope,
  view,
  onChange,
}: {
  data: GraphResponse
  scope: GraphScope
  view: GraphView
  onChange: (view: GraphView) => void
}) {
  const { types, degree } = scope
  const byId = useMemo(() => new Map(data.nodes.map((n) => [n.canonical_id, n])), [data])
  const maxMembers = useMemo(() => data.nodes.reduce((m, n) => Math.max(m, n.members), 1), [data])
  const hubs = useMemo(() => new Set(scope.clusters.map((c) => c.hub.canonical_id)), [scope])
  const unlinkedByType = useMemo(() => {
    const counts = new Map<string, number>()
    for (const n of scope.unlinked) counts.set(n.entity_type, (counts.get(n.entity_type) ?? 0) + 1)
    return [...counts].sort((a, b) => b[1] - a[1])
  }, [scope])

  const { rootRef, hover, show, hide } = useHover()
  const width = useWidth(rootRef)
  const focused = scope.clusters.find((c) => c.hub.canonical_id === view.focus)

  const laid = useMemo(() => {
    if (width === 0) return EMPTY_LAYOUT
    if (focused) {
      let step = FOCUS_RING_STEP
      let sun = layoutSun(focused, degree, maxMembers, step, Infinity)
      while (sun.bounds.x1 - sun.bounds.x0 > width && step > RING_STEP) {
        step = Math.max(RING_STEP, step * 0.85)
        sun = layoutSun(focused, degree, maxMembers, step, Infinity)
      }
      const w = sun.bounds.x1 - sun.bounds.x0
      return { suns: [{ sun, ox: (width - w) / 2 - sun.bounds.x0, oy: -sun.bounds.y0 }], height: sun.bounds.y1 - sun.bounds.y0 }
    }
    const half = (width - GUTTER) / 2
    const suns = scope.clusters.map((c) => {
      const labelDepth = c.nodes.length <= LABEL_ALL_MAX ? Infinity : 0
      const sun = layoutSun(c, degree, maxMembers, RING_STEP, labelDepth)
      const tooWide = labelDepth > 1 && sun.bounds.x1 - sun.bounds.x0 > half
      return tooWide ? layoutSun(c, degree, maxMembers, RING_STEP, 1) : sun
    })
    return tile(suns, width)
  }, [scope, focused, degree, maxMembers, width])

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
      if (!e.ctrlKey && !e.metaKey) return
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
  }, [laid.height])

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
    if (d.moved) setPan((v) => ({ ...v, x: d.px + dx, y: d.py + dy }))
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
  const focusOn = (id: string) => {
    setSelected(id)
    onChange({ ...view, focus: id })
  }

  const selectedNode = selected ? byId.get(selected) : undefined
  const selectedEdges = useMemo(
    () => (selected ? data.edges.filter((e) => e.from === selected || e.to === selected) : []),
    [data, selected],
  )

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="min-w-0 flex-1">
        {scope.unlinked.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs text-dbb-muted">
            <span className="mr-1">{scope.unlinked.length} unlinked:</span>
            {unlinkedByType.map(([t, n]) => (
              <TypeChip key={t} type={t} color={typeColor(t, types)}>
                {n}
              </TypeChip>
            ))}
          </div>
        )}
        <div ref={rootRef} className="relative overflow-hidden rounded-lg border border-dbb-warm bg-white">
          {width > 0 && laid.suns.length === 0 ? (
            <Empty>No links among the visible types.</Empty>
          ) : (
            <svg
              ref={svgRef}
              viewBox={`0 0 ${width || 1} ${laid.height || 1}`}
              style={{ height: laid.height || 1 }}
              className="w-full cursor-grab select-none active:cursor-grabbing"
              role="img"
              aria-label={`Knowledge graph of ${scope.clusters.length} clusters`}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={() => {
                onMouseUp()
                hide()
              }}
            >
              <g transform={`translate(${pan.x} ${pan.y}) scale(${pan.k})`}>
                {laid.suns.map(({ sun, ox, oy }) => (
                  <g key={sun.hub.canonical_id} transform={`translate(${ox} ${oy})`}>
                    <circle r={sun.radius} fill="none" stroke="#E0DCC1" strokeDasharray="4 4" />
                    <text
                      y={-sun.radius - 8}
                      textAnchor="middle"
                      className="cursor-pointer fill-dbb-charcoal text-[11px] font-medium"
                      onClick={() => {
                        if (!dragged.current) focusOn(sun.hub.canonical_id)
                      }}
                    >
                      {sun.heading}
                    </text>
                    {sun.links.map((l, i) => {
                      const lit = selected !== null && (l.a.node.canonical_id === selected || l.b.node.canonical_id === selected)
                      return (
                        <g
                          key={i}
                          onMouseMove={(e) =>
                            show(e, l.edge.rel, [`${displayLabel(l.a.node)} → ${displayLabel(l.b.node)}`, l.edge.grounding])
                          }
                          onMouseLeave={hide}
                        >
                          <line
                            x1={l.a.x}
                            y1={l.a.y}
                            x2={l.b.x}
                            y2={l.b.y}
                            stroke={lit ? '#1A1A1A' : '#E0DCC1'}
                            strokeOpacity={0.9}
                            strokeWidth={lit ? 1.5 : 1}
                          />
                          <line x1={l.a.x} y1={l.a.y} x2={l.b.x} y2={l.b.y} stroke="transparent" strokeWidth={8} />
                        </g>
                      )
                    })}
                    {sun.dots.map((d) => {
                      const id = d.node.canonical_id
                      const color = typeColor(d.node.entity_type, types)
                      return (
                        <g key={id}>
                          {d.depth === 0 && <circle cx={d.x} cy={d.y} r={d.r + 3.5} fill="none" stroke={color} strokeOpacity={0.35} />}
                          <circle
                            cx={d.x}
                            cy={d.y}
                            r={d.r}
                            fill={color}
                            stroke={selected === id ? '#1A1A1A' : '#FFFFFF'}
                            strokeWidth={selected === id ? 2 : 1.5}
                            className="cursor-pointer"
                            onMouseMove={(e) =>
                              show(e, displayLabel(d.node), [
                                d.node.entity_type,
                                `${d.node.members} members · degree ${d.degree}`,
                              ])
                            }
                            onMouseLeave={hide}
                            onClick={() => {
                              if (!dragged.current) setSelected(id)
                            }}
                          />
                        </g>
                      )
                    })}
                    {sun.labels.map((l) => (
                      <text
                        key={l.id}
                        x={l.x}
                        y={l.y}
                        textAnchor={l.anchor}
                        paintOrder="stroke"
                        stroke="#FFFFFF"
                        strokeWidth={3}
                        strokeLinejoin="round"
                        className={`pointer-events-none text-[10px] ${l.strong ? 'fill-dbb-charcoal' : 'fill-dbb-muted'}`}
                      >
                        {l.text}
                      </text>
                    ))}
                  </g>
                ))}
              </g>
            </svg>
          )}
          <HoverTip hover={hover} width={width} />
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {types.map((t) => (
            <TypeChip
              key={t}
              type={t}
              color={typeColor(t, types)}
              active={!view.hidden.has(t)}
              onClick={() => toggleType(t)}
            >
              {data.counts.by_type[t]}
            </TypeChip>
          ))}
        </div>
      </div>
      <aside className="shrink-0 rounded-lg border border-dbb-warm bg-dbb-surface p-4 lg:w-[280px]">
        {selectedNode ? (
          <NodePanel
            node={selectedNode}
            degree={degree.get(selectedNode.canonical_id) ?? 0}
            edges={selectedEdges}
            byId={byId}
            hubs={hubs}
            types={types}
            onSelect={setSelected}
            onFocus={focusOn}
          />
        ) : (
          <p className="text-xs text-dbb-muted">
            Each dashed circle is one cluster, named after its hub. Click a node to see its edges; click a cluster name to
            focus it. Drag to pan, ⌘-wheel to zoom.
          </p>
        )}
      </aside>
    </div>
  )
}
