import type { Node } from '@xyflow/react'
import type { CanvasNode, Kind } from '@/api'
import { addDays } from '@/lib/calendar'

export const PRESETS = ['all', 'today', 'yesterday', 'last7', 'last30', 'custom'] as const

export type Preset = (typeof PRESETS)[number]

export const PRESET_LABELS: Record<Preset, string> = {
  all: 'All time',
  today: 'Today',
  yesterday: 'Yesterday',
  last7: 'Last 7 days',
  last30: 'Last 30 days',
  custom: 'Custom',
}

export interface Bounds {
  from?: string
  to?: string
}

export type Range = { preset: Exclude<Preset, 'custom'> } | ({ preset: 'custom' } & Required<Bounds>)

export const DEFAULT_RANGE: Range = { preset: 'all' }

export function bounds(range: Range, today: string): Bounds {
  switch (range.preset) {
    case 'all':
      return {}
    case 'today':
      return { from: today, to: today }
    case 'yesterday': {
      const yesterday = addDays(today, -1)
      return { from: yesterday, to: yesterday }
    }
    case 'last7':
      return { from: addDays(today, -6), to: today }
    case 'last30':
      return { from: addDays(today, -29), to: today }
    case 'custom':
      return { from: range.from, to: range.to }
  }
}

export const CHIPS = ['image', 'document', 'carousel'] as const

export type Chip = (typeof CHIPS)[number]

export const CHIP_LABELS: Record<Chip, string> = { image: 'Images', document: 'Documents', carousel: 'Carousels' }

export const chipOf = (kind: Kind): Chip => (kind === 'image' || kind === 'carousel' ? kind : 'document')

export const toggle = <T>(items: T[], item: T) => (items.includes(item) ? items.filter((x) => x !== item) : [...items, item])

export function filterNodes(nodes: CanvasNode[], chips: Chip[], search: string): CanvasNode[] {
  const needle = search.trim().toLowerCase()
  return nodes.filter(
    (node) => (chips.length === 0 || chips.includes(chipOf(node.kind))) && (!needle || node.label.toLowerCase().includes(needle)),
  )
}

export const isPicture = (node: CanvasNode) => !!node.url && node.media_type.startsWith('image/')

export const KIND_COLORS: Record<Kind, string> = {
  post: '#1A1A1A',
  newsletter: '#807F74',
  blog: '#5D8A5D',
  image: '#FD4E00',
  carousel: '#C0625A',
}

export const DAY_COLOR = '#E0DCC1'

export const CARD = { width: 176, height: 184 }

export const HEADER_HEIGHT = 40

const GAP = 16

const COLUMNS = 3

const COLUMN_GAP = 48

export const COLUMN_WIDTH = COLUMNS * CARD.width + (COLUMNS - 1) * GAP

export type AssetFlowNode = Node<{ node: CanvasNode }, 'asset'>

export type DayFlowNode = Node<{ date: string; count: number }, 'day'>

export type FlowNode = AssetFlowNode | DayFlowNode

export function groupByDate(nodes: CanvasNode[]): [string, CanvasNode[]][] {
  const groups = new Map<string, CanvasNode[]>()
  for (const node of nodes) groups.set(node.date, [...(groups.get(node.date) ?? []), node])
  return [...groups.entries()].sort(([a], [b]) => (a < b ? 1 : a > b ? -1 : 0))
}

const inert = { draggable: false, selectable: false, connectable: false, focusable: false }

const clickable = { ...inert, selectable: true }

export function buildNodes(groups: [string, CanvasNode[]][]): FlowNode[] {
  return groups.flatMap(([date, nodes], column) => {
    const left = column * (COLUMN_WIDTH + COLUMN_GAP)
    const header: DayFlowNode = {
      id: `day:${date}`,
      type: 'day',
      position: { x: left, y: 0 },
      width: COLUMN_WIDTH,
      height: HEADER_HEIGHT,
      data: { date, count: nodes.length },
      ...inert,
    }
    const cards: AssetFlowNode[] = nodes.map((node, i) => ({
      id: node.id,
      type: 'asset',
      position: {
        x: left + (i % COLUMNS) * (CARD.width + GAP),
        y: HEADER_HEIGHT + Math.floor(i / COLUMNS) * (CARD.height + GAP),
      },
      ...CARD,
      data: { node },
      ...clickable,
    }))
    return [header, ...cards]
  })
}

export const nodeColor = (node: FlowNode) => (node.type === 'asset' ? KIND_COLORS[node.data.node.kind] : DAY_COLOR)
