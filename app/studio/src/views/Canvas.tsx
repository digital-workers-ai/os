import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { asApiError, getCanvas, type CanvasNode } from '@/api'
import { Filters } from '@/components/canvas/Filters'
import { Menu, type MenuState } from '@/components/canvas/Menu'
import { nodeTypes } from '@/components/canvas/Node'
import { Preview } from '@/components/canvas/Preview'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { todayIso } from '@/lib/calendar'
import { bounds, buildNodes, DEFAULT_RANGE, filterNodes, groupByDate, nodeColor, type Chip, type FlowNode, type Range } from '@/lib/canvas'

const link = 'text-ink underline underline-offset-2'

function Refit({ signature }: { signature: string }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    void fitView()
  }, [signature, fitView])
  return null
}

export function Canvas() {
  const [today] = useState(todayIso)
  const [range, setRange] = useState<Range>(DEFAULT_RANGE)
  const [chips, setChips] = useState<Chip[]>([])
  const [search, setSearch] = useState('')
  const [preview, setPreview] = useState<number | null>(null)
  const [menu, setMenu] = useState<MenuState | null>(null)
  const { from, to } = bounds(range, today)
  const query = useQuery({ queryKey: ['canvas', from, to], queryFn: () => getCanvas(from, to) })
  const nodes = query.data?.nodes
  const groups = useMemo(() => groupByDate(filterNodes(nodes ?? [], chips, search)), [nodes, chips, search])
  const ordered = useMemo(() => groups.flatMap(([, group]) => group), [groups])
  const flowNodes = useMemo(() => buildNodes(groups), [groups])
  const closeMenu = useCallback(() => setMenu(null), [])
  const openPreview = (node: CanvasNode) => {
    setMenu(null)
    setPreview(ordered.findIndex((n) => n.id === node.id))
  }
  const onDoubleClick: NodeMouseHandler<FlowNode> = (_, node) => {
    if (node.type === 'asset') openPreview(node.data.node)
  }
  const onContextMenu: NodeMouseHandler<FlowNode> = (event, node) => {
    event.preventDefault()
    if (node.type === 'asset') setMenu({ x: event.clientX, y: event.clientY, node: node.data.node })
  }
  const state = query.isPending ? 'loading' : query.isError ? 'error' : 'ready'

  return (
    <ReactFlowProvider>
      <div className="flex flex-col gap-4" data-testid="canvas-view" data-state={state}>
        <Filters range={range} today={today} onRange={setRange} chips={chips} onChips={setChips} search={search} onSearch={setSearch} />
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorBanner error={asApiError(query.error)} />
        ) : query.data.nodes.length === 0 && range.preset === 'all' ? (
          <Card data-testid="canvas-empty">
            <p className="text-sm text-muted">
              Nothing has been made yet.{' '}
              <Link to="/create" className={link} data-testid="canvas-empty-create">
                Make something
              </Link>{' '}
              or{' '}
              <Link to="/calendar" className={link} data-testid="canvas-empty-calendar">
                fill the calendar
              </Link>
              .
            </p>
          </Card>
        ) : ordered.length === 0 ? (
          <Empty testId="canvas-no-match">nothing matches</Empty>
        ) : (
          <div className="h-[calc(100vh-14rem)] min-h-[420px] overflow-hidden rounded-xl border border-line bg-paper" data-testid="canvas-board">
            <ReactFlow<FlowNode>
              nodes={flowNodes}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.1}
              maxZoom={2}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              zoomOnDoubleClick={false}
              onNodeDoubleClick={onDoubleClick}
              onNodeContextMenu={onContextMenu}
              onPaneClick={closeMenu}
            >
              <Background variant={BackgroundVariant.Dots} />
              <Controls showInteractive={false} />
              <MiniMap<FlowNode> nodeColor={nodeColor} pannable zoomable />
              <Refit signature={ordered.map((n) => n.id).join('|')} />
            </ReactFlow>
          </div>
        )}
        <Preview nodes={ordered} index={preview} onStep={setPreview} onClose={() => setPreview(null)} />
        <Menu menu={menu} onOpen={openPreview} onClose={closeMenu} />
      </div>
    </ReactFlowProvider>
  )
}
