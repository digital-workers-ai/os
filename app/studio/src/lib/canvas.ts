import { MarkerType, type Edge, type Node, type XYPosition } from '@xyflow/react'
import type { CanvasEdge, CanvasNode } from '@/api'
import { shortDate } from '@/lib/format'

export const NODE_WIDTH = 152
export const NODE_HEIGHT = 96
export const NODE_GAP = 16
export const NODES_PER_ROW = 3
export const BOX_PADDING = 16
export const BOX_HEADER = 34
export const DATE_HEADER = 40
export const COLUMN_GAP = 40
export const FRAME_ROWS = 2

const INK = '#1A1A1A'
const PAPER = '#FFFFFF'
const MUTED = '#807F74'

export type FrameTone = 'date' | 'group' | 'campaign'

export type FrameSpec = { id: string; label: string; nodes: string[] }

export type Layout = Record<string, XYPosition>

export type FileFlowNode = Node<{ node: CanvasNode }, 'file'>

export type FrameFlowNode = Node<{ label: string; tone: FrameTone }, 'frame'>

export type CanvasFlowNode = FileFlowNode | FrameFlowNode

export type FrameBox = { id: string; x: number; y: number; width: number; height: number }

export type DateColumn = { date: string; groups: { group: string; nodes: CanvasNode[] }[] }

export function groupByDate(nodes: CanvasNode[]): DateColumn[] {
  const dates = new Map<string, Map<string, CanvasNode[]>>()
  for (const node of nodes) {
    const groups = dates.get(node.date) ?? new Map<string, CanvasNode[]>()
    groups.set(node.group, [...(groups.get(node.group) ?? []), node])
    dates.set(node.date, groups)
  }
  return [...dates.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([date, groups]) => ({ date, groups: [...groups.entries()].map(([group, nodes]) => ({ group, nodes })) }))
}

const columnsFor = (count: number) => Math.min(Math.max(count, 1), NODES_PER_ROW)

const rowsFor = (count: number) => Math.max(Math.ceil(count / NODES_PER_ROW), 1)

export const boxWidth = (count: number) => BOX_PADDING * 2 + columnsFor(count) * NODE_WIDTH + (columnsFor(count) - 1) * NODE_GAP

export const boxHeight = (count: number) => BOX_HEADER + rowsFor(count) * NODE_HEIGHT + (rowsFor(count) - 1) * NODE_GAP + BOX_PADDING

const slotAt = (index: number): XYPosition => ({
  x: BOX_PADDING + (index % NODES_PER_ROW) * (NODE_WIDTH + NODE_GAP),
  y: BOX_HEADER + Math.floor(index / NODES_PER_ROW) * (NODE_HEIGHT + NODE_GAP),
})

const boxNode = (id: string, label: string, tone: FrameTone, position: XYPosition, width: number, height: number): FrameFlowNode => ({
  id,
  type: 'frame',
  position,
  width,
  height,
  data: { label, tone },
})

const fileNode = (node: CanvasNode, parentId: string, position: XYPosition): FileFlowNode => ({
  id: node.id,
  type: 'file',
  parentId,
  extent: 'parent',
  position,
  width: NODE_WIDTH,
  height: NODE_HEIGHT,
  data: { node },
})

export function buildNodes(nodes: CanvasNode[], frames: FrameSpec[], layout: Layout): CanvasFlowNode[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const claimed = new Set(frames.flatMap((frame) => frame.nodes))
  const built: CanvasFlowNode[] = []
  let columnX = 0

  for (const column of groupByDate(nodes.filter((node) => !claimed.has(node.id)))) {
    const dateId = `date:${column.date}`
    const widest = Math.max(...column.groups.map((group) => boxWidth(group.nodes.length)))
    const stacked = column.groups.reduce((total, group) => total + boxHeight(group.nodes.length), 0)
    const dateWidth = BOX_PADDING * 2 + widest
    const dateHeight = DATE_HEADER + stacked + (column.groups.length - 1) * NODE_GAP + BOX_PADDING
    built.push(boxNode(dateId, shortDate(column.date), 'date', layout[dateId] ?? { x: columnX, y: 0 }, dateWidth, dateHeight))
    let groupY = DATE_HEADER
    for (const group of column.groups) {
      const groupId = `group:${column.date}:${group.group}`
      const width = boxWidth(group.nodes.length)
      const height = boxHeight(group.nodes.length)
      built.push({
        ...boxNode(groupId, group.group, 'group', layout[groupId] ?? { x: BOX_PADDING, y: groupY }, width, height),
        parentId: dateId,
        extent: 'parent',
      })
      group.nodes.forEach((node, index) => built.push(fileNode(node, groupId, layout[node.id] ?? slotAt(index))))
      groupY += height + NODE_GAP
    }
    columnX += dateWidth + COLUMN_GAP
  }

  let frameY = 0
  for (const frame of frames) {
    const members = frame.nodes.map((id) => byId.get(id)).filter((node): node is CanvasNode => node !== undefined)
    const width = boxWidth(NODES_PER_ROW)
    const height = boxHeight(Math.max(members.length, NODES_PER_ROW * FRAME_ROWS))
    built.push(boxNode(frame.id, frame.label, 'campaign', layout[frame.id] ?? { x: columnX, y: frameY }, width, height))
    members.forEach((node, index) => built.push(fileNode(node, frame.id, layout[node.id] ?? slotAt(index))))
    frameY += height + NODE_GAP
  }

  return built
}

const RELATIONS: Record<CanvasEdge['rel'], Pick<Edge, 'style' | 'markerEnd'>> = {
  ancestor: {
    style: { stroke: MUTED, strokeWidth: 1, strokeDasharray: '5 4' },
    markerEnd: { type: MarkerType.Arrow, color: MUTED, width: 16, height: 16 },
  },
  draft: {
    style: { stroke: MUTED, strokeWidth: 1 },
    markerEnd: { type: MarkerType.Arrow, color: MUTED, width: 16, height: 16 },
  },
  build: {
    style: { stroke: INK, strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color: INK, width: 18, height: 18 },
  },
}

export function buildEdges(edges: CanvasEdge[], present: Set<string>): Edge[] {
  return edges
    .filter((edge) => present.has(edge.from) && present.has(edge.to))
    .map((edge) => ({
      id: `${edge.rel}:${edge.from}:${edge.to}`,
      source: edge.from,
      target: edge.to,
      type: 'smoothstep',
      label: edge.rel,
      labelShowBg: true,
      labelStyle: { fontSize: 10, fill: MUTED },
      labelBgStyle: { fill: PAPER },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 4,
      ...RELATIONS[edge.rel],
    }))
}

export const campaignBoxes = (nodes: CanvasFlowNode[]): FrameBox[] =>
  nodes
    .filter((node): node is FrameFlowNode => node.type === 'frame' && node.data.tone === 'campaign')
    .map((node) => ({ id: node.id, x: node.position.x, y: node.position.y, width: node.width ?? 0, height: node.height ?? 0 }))

export const frameAt = (point: XYPosition, boxes: FrameBox[]): string | null =>
  [...boxes]
    .reverse()
    .find((box) => point.x >= box.x && point.x <= box.x + box.width && point.y >= box.y && point.y <= box.y + box.height)?.id ?? null

export const matching = (nodes: CanvasNode[], search: string): CanvasNode[] => {
  const needle = search.trim().toLowerCase()
  if (needle === '') return nodes
  return nodes.filter((node) => [node.label, node.group, node.kind].some((field) => field.toLowerCase().includes(needle)))
}

export const monthRange = (month: string): { from: string; to: string } | null => {
  if (month === '') return null
  const [year, index] = month.split('-').map(Number)
  const last = new Date(Date.UTC(year, index, 0)).getUTCDate()
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, '0')}` }
}

export const positions = (nodes: CanvasFlowNode[]): Record<string, { x: number; y: number }> =>
  Object.fromEntries(nodes.map((node) => [node.id, { x: Math.round(node.position.x), y: Math.round(node.position.y) }]))
