import { useEffect, useLayoutEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type RefObject } from 'react'
import { Empty } from '@/components/ui/empty'
import { HoverTip, typeColor, useHover } from './shared'

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

export interface Cluster {
  hub: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphScope {
  types: string[]
  maxMembers: number
  byId: Map<string, GraphNode>
  edgesOf: Map<string, GraphEdge[]>
}

const RING_STEP = 56 // min hub-to-spoke radius, px, overview suns
const FOCUS_RING_STEP = 110 // starting radius for the focused sun, shrinks to fit
const ARC_SPACING = 22 // min arc between neighbouring spokes, px
const LABEL_ALL_MAX = 12 // suns this small label every spoke
const LABEL_CHARS = 22 // labels longer than this get an ellipsis
const SUN_PAD = 10 // padding around a sun's bounding box, px
const GUTTER = 20 // gap between tiled suns, px

export const displayLabel = (n: GraphNode) => (n.label === n.anchor ? n.anchor.slice(n.anchor.lastIndexOf('|') + 1) : n.label)

const truncate = (s: string) => (s.length > LABEL_CHARS ? `${s.slice(0, LABEL_CHARS - 1)}…` : s)

export function scopeGraph(data: GraphResponse): GraphScope {
  const byId = new Map(data.nodes.map((n) => [n.canonical_id, n]))
  const edgesOf = new Map<string, GraphEdge[]>()
  for (const e of data.edges.filter((e) => byId.has(e.from) && byId.has(e.to))) {
    for (const id of [e.from, e.to]) {
      if (!edgesOf.has(id)) edgesOf.set(id, [])
      edgesOf.get(id)!.push(e)
    }
  }
  return {
    types: Object.keys(data.counts.by_type).sort(),
    maxMembers: data.nodes.reduce((m, n) => Math.max(m, n.members), 1),
    byId,
    edgesOf,
  }
}

const sunFor = (scope: GraphScope, hub: GraphNode): Cluster => {
  const edges = scope.edgesOf.get(hub.canonical_id) ?? []
  const others = new Set(edges.map((e) => (e.from === hub.canonical_id ? e.to : e.from)))
  return { hub, nodes: [hub, ...[...others].map((id) => scope.byId.get(id)!)], edges }
}

export const hubsOf = (scope: GraphScope, type: string) =>
  [...scope.byId.values()]
    .filter((n) => n.entity_type === type)
    .map((hub) => sunFor(scope, hub))
    .sort((a, b) => b.edges.length - a.edges.length || displayLabel(a.hub).localeCompare(displayLabel(b.hub)))

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
}

interface Link {
  a: Dot
  b: Dot
  edge: GraphEdge
}

interface Label extends Spot {
  id: string
  text: string
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

interface Layout {
  suns: PlacedSun[]
  x: number
  y: number
  k: number
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

function layoutSun(cluster: Cluster, scope: GraphScope, step: number, labelled: boolean): Sun {
  const { hub } = cluster
  const spokes = cluster.nodes
    .filter((n) => n !== hub)
    .sort((a, b) => a.entity_type.localeCompare(b.entity_type) || displayLabel(a).localeCompare(displayLabel(b)))
  const ring = spokes.length ? Math.max(step, (spokes.length * ARC_SPACING) / (2 * Math.PI)) : 0
  const dot = (node: GraphNode, angle: number, dist: number): Dot => ({
    node,
    x: dist * Math.cos(angle),
    y: dist * Math.sin(angle),
    r: 5 + (6 * (node.members - 1)) / Math.max(1, scope.maxMembers - 1),
    angle,
  })
  const dots = [dot(hub, 0, 0), ...spokes.map((n, i) => dot(n, -Math.PI / 2 + (2 * Math.PI * (i + 0.5)) / spokes.length, ring))]
  const dotById = new Map(dots.map((d) => [d.node.canonical_id, d]))
  const links = cluster.edges.map((edge) => ({ a: dotById.get(edge.from)!, b: dotById.get(edge.to)!, edge }))
  const radius = ring + Math.max(...dots.map((d) => d.r)) + 8
  const heading = truncate(displayLabel(hub))
  const headingBox = textBox({ x: 0, y: -radius - 8, anchor: 'middle' }, heading, 11)
  const taken: Box[] = [headingBox]
  const labels: Label[] = []
  for (const d of labelled ? dots.slice(1) : []) {
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
      labels.push({ id: d.node.canonical_id, text, ...spot })
      break
    }
  }
  const bounds: Box = { x0: -radius, y0: headingBox.y0, x1: radius, y1: radius }
  for (const t of taken) grow(bounds, t)
  bounds.x0 -= SUN_PAD
  bounds.y0 -= SUN_PAD
  bounds.x1 += SUN_PAD
  bounds.y1 += SUN_PAD
  return { hub, heading, radius, dots, links, labels, bounds }
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
  let used = 0
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
    used = Math.max(used, x + w)
    height = Math.max(height, y + h)
  }
  return { suns: placed, width: used, height }
}

function fitTiles(suns: Sun[], width: number, height: number): Layout {
  let k = 1
  let laid = tile(suns, width)
  if (laid.height > height) {
    k = Math.sqrt(height / laid.height)
    laid = tile(suns, width / k)
    k = Math.min(k, height / laid.height)
  }
  return { suns: laid.suns, x: (width - laid.width * k) / 2, y: (height - laid.height * k) / 2, k }
}

function fitFocus(cluster: Cluster, scope: GraphScope, width: number, height: number): Layout {
  const fits = (s: Sun) => s.bounds.x1 - s.bounds.x0 <= width && s.bounds.y1 - s.bounds.y0 <= height
  let step = FOCUS_RING_STEP
  let sun = layoutSun(cluster, scope, step, true)
  while (!fits(sun) && step > RING_STEP) {
    step = Math.max(RING_STEP, step * 0.85)
    sun = layoutSun(cluster, scope, step, true)
  }
  const w = sun.bounds.x1 - sun.bounds.x0
  const h = sun.bounds.y1 - sun.bounds.y0
  const k = Math.min(1, width / w, height / h)
  return { suns: [{ sun, ox: -sun.bounds.x0, oy: -sun.bounds.y0 }], x: (width - w * k) / 2, y: (height - h * k) / 2, k }
}

const EMPTY_LAYOUT: Layout = { suns: [], x: 0, y: 0, k: 1 }

function useSize(ref: RefObject<HTMLElement>) {
  const [size, setSize] = useState({ width: 0, height: 0 })
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: Math.round(entry.contentRect.width), height: Math.round(entry.contentRect.height) }),
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])
  return size
}

export function Canvas({
  scope,
  clusters,
  focused,
  selected,
  onSelect,
}: {
  scope: GraphScope
  clusters: Cluster[]
  focused: boolean
  selected: string | null
  onSelect: (id: string) => void
}) {
  const { rootRef, hover, show, hide } = useHover()
  const { width, height } = useSize(rootRef)

  const laid = useMemo(() => {
    if (!width || !height || clusters.length === 0) return EMPTY_LAYOUT
    if (focused) return fitFocus(clusters[0], scope, width, height)
    return fitTiles(
      clusters.map((c) => layoutSun(c, scope, RING_STEP, c.nodes.length <= LABEL_ALL_MAX)),
      width,
      height,
    )
  }, [scope, clusters, focused, width, height])

  const [pan, setPan] = useState({ x: 0, y: 0, k: 1 })
  const svgRef = useRef<SVGSVGElement>(null)
  const baseRef = useRef<SVGGElement>(null)
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
      const ctm = baseRef.current?.getScreenCTM()
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
    const scale = baseRef.current?.getScreenCTM()?.a ?? 1
    const dx = (e.clientX - d.x) / scale
    const dy = (e.clientY - d.y) / scale
    if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true
    if (d.moved) setPan((v) => ({ ...v, x: d.px + dx, y: d.py + dy }))
  }
  const onMouseUp = () => {
    dragged.current = drag.current?.moved ?? false
    drag.current = null
  }
  const pick = (id: string) => {
    if (!dragged.current) onSelect(id)
  }

  return (
    <div ref={rootRef} className="relative h-96 overflow-hidden rounded-lg border border-dbb-warm bg-white lg:h-auto lg:min-h-0 lg:flex-1">
      <svg
        ref={svgRef}
        className="absolute inset-0 h-full w-full cursor-grab select-none active:cursor-grabbing"
        role="img"
        aria-label="Knowledge graph"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={() => {
          onMouseUp()
          hide()
        }}
      >
        <g ref={baseRef} transform={`translate(${laid.x} ${laid.y}) scale(${laid.k})`}>
          <g transform={`translate(${pan.x} ${pan.y}) scale(${pan.k})`}>
            {laid.suns.map(({ sun, ox, oy }) => (
              <g key={sun.hub.canonical_id} transform={`translate(${ox} ${oy})`}>
                <circle r={sun.radius} fill="none" stroke="#E0DCC1" strokeDasharray="4 4" />
                <text
                  y={-sun.radius - 8}
                  textAnchor="middle"
                  className="cursor-pointer fill-dbb-charcoal text-[11px] font-medium"
                  onClick={() => pick(sun.hub.canonical_id)}
                >
                  {sun.heading}
                </text>
                {sun.links.map((l, i) => {
                  const lit = selected !== null && (l.a.node.canonical_id === selected || l.b.node.canonical_id === selected)
                  return (
                    <g
                      key={i}
                      onMouseMove={(e) => show(e, l.edge.rel, [`${displayLabel(l.a.node)} → ${displayLabel(l.b.node)}`, l.edge.grounding])}
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
                  const color = typeColor(d.node.entity_type, scope.types)
                  return (
                    <g key={id}>
                      {d.node === sun.hub && <circle cx={d.x} cy={d.y} r={d.r + 3.5} fill="none" stroke={color} strokeOpacity={0.35} />}
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
                            `${d.node.members} members · degree ${scope.edgesOf.get(id)?.length ?? 0}`,
                          ])
                        }
                        onMouseLeave={hide}
                        onClick={() => pick(id)}
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
                    className="pointer-events-none fill-dbb-muted text-[10px]"
                  >
                    {l.text}
                  </text>
                ))}
              </g>
            ))}
          </g>
        </g>
      </svg>
      {width > 0 && clusters.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Empty>no links</Empty>
        </div>
      )}
      <HoverTip hover={hover} width={width} />
    </div>
  )
}
