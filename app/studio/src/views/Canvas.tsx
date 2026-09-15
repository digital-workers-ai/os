import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Background,
  Controls,
  Handle,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type NodeProps,
  type NodeTypes,
  type OnNodeDrag,
} from '@xyflow/react'
import { asApiError, getCanvas, saveLayout, type CanvasNode } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import {
  buildEdges,
  buildNodes,
  campaignBoxes,
  frameAt,
  matching,
  monthRange,
  positions,
  type CanvasFlowNode,
  type FileFlowNode,
  type FrameFlowNode,
  type FrameSpec,
  type Layout,
} from '@/lib/canvas'
import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const SELECT = 'h-8 rounded-md border border-line bg-paper px-2 text-xs text-ink'

const HANDLE = '!h-1.5 !w-1.5 !min-h-0 !min-w-0 !rounded-full !border !border-line !bg-wash'

const GLYPHS: Record<string, string> = { image: '▣', html: '</>', document: '▤' }

const glyph = (kind: string) => GLYPHS[kind] ?? '▫'

const TONES = {
  date: 'border-line bg-surface/70',
  group: 'border-line/70 bg-paper/70',
  campaign: 'border-dashed border-line bg-wash/40',
}

const LINEAGE = [
  { rel: 'ancestor', stroke: '#807F74', width: 1, dash: '5 4' },
  { rel: 'draft', stroke: '#807F74', width: 1, dash: undefined },
  { rel: 'build', stroke: '#1A1A1A', width: 2, dash: undefined },
]

const LOCAL_FRAME = 'frame:local:'

function FileNode({ data }: NodeProps<FileFlowNode>) {
  const node = data.node
  return (
    <div
      className="flex h-full w-full flex-col gap-1.5 overflow-hidden rounded-xl border border-line bg-paper p-2 shadow-sm"
      data-testid="canvas-node"
      data-id={node.id}
      data-kind={node.kind}
    >
      <Handle type="target" position={Position.Left} className={HANDLE} />
      {node.kind === 'image' && node.url !== null ? (
        <img src={node.url} alt="" className="min-h-0 w-full flex-1 rounded-md bg-wash object-cover" />
      ) : (
        <span className="flex min-h-0 flex-1 items-center justify-center rounded-md bg-wash text-lg text-muted">{glyph(node.kind)}</span>
      )}
      <span className="block truncate text-[11px] font-medium text-ink" title={node.label}>
        {node.label}
      </span>
      <Handle type="source" position={Position.Right} className={HANDLE} />
    </div>
  )
}

function FrameNode({ id, data }: NodeProps<FrameFlowNode>) {
  return (
    <div
      className={cn('h-full w-full rounded-xl border px-3 py-2', TONES[data.tone])}
      data-testid="canvas-frame"
      data-frame-id={id}
      data-tone={data.tone}
    >
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted">{data.label}</span>
    </div>
  )
}

const NODE_TYPES: NodeTypes = { file: FileNode, frame: FrameNode }

const MediaBox = ({ children }: { children: ReactNode }) => (
  <p className="flex h-32 items-center justify-center rounded-lg border border-dashed border-line bg-wash/40 text-xs text-muted">{children}</p>
)

function Media({ node }: { node: CanvasNode }) {
  if (node.url === null) return <MediaBox>{node.media_type} — nothing stored to show</MediaBox>
  if (node.kind === 'image') return <img src={node.url} alt={node.label} className="max-h-72 w-full rounded-lg border border-line object-contain" />
  if (node.kind === 'html') return <iframe title={node.label} src={node.url} className="h-72 w-full rounded-lg border border-line bg-paper" />
  return <MediaBox>{node.media_type}</MediaBox>
}

function Preview({ node, onClose }: { node: CanvasNode | null; onClose: () => void }) {
  return (
    <Dialog
      open={node !== null}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      {node !== null && (
        <DialogContent data-testid="canvas-preview">
          <DialogTitle className="break-all">{node.label}</DialogTitle>
          <Media node={node} />
          <dl className="grid grid-cols-[4.5rem_1fr] gap-y-1 text-xs">
            <dt className="text-muted">group</dt>
            <dd className="min-w-0 break-words text-ink">{node.group}</dd>
            <dt className="text-muted">date</dt>
            <dd className="text-ink">{shortDate(node.date)}</dd>
            <dt className="text-muted">media</dt>
            <dd>
              <Mono className="text-muted">{node.media_type}</Mono>
            </dd>
          </dl>
          {(node.asset_seq !== null || node.proposal_seq !== null) && (
            <div className="flex flex-wrap gap-2">
              {node.asset_seq !== null && (
                <Link to={`/assets/${node.asset_seq}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                  Asset #{node.asset_seq}
                </Link>
              )}
              {node.proposal_seq !== null && (
                <Link to={`/proposals/${node.proposal_seq}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                  Proposal #{node.proposal_seq}
                </Link>
              )}
            </div>
          )}
          <DialogClose asChild>
            <Button size="sm" className="mt-auto self-start" data-testid="canvas-preview-close">
              Close
            </Button>
          </DialogClose>
        </DialogContent>
      )}
    </Dialog>
  )
}

function Board() {
  const [month, setMonth] = useState('')
  const [kind, setKind] = useState('')
  const [skill, setSkill] = useState('')
  const [search, setSearch] = useState('')
  const [frames, setFrames] = useState<FrameSpec[]>([])
  const [moved, setMoved] = useState<Layout>({})
  const [open, setOpen] = useState<CanvasNode | null>(null)
  const [saved, setSaved] = useState(false)
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasFlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const flow = useReactFlow<CanvasFlowNode, Edge>()

  const range = monthRange(month)
  const query = useQuery({
    queryKey: ['canvas', month, kind, skill],
    queryFn: () => getCanvas(range?.from, range?.to, kind || undefined, skill || undefined),
  })
  const data = query.data
  const shown = useMemo(() => matching(data?.nodes ?? [], search), [data, search])

  useEffect(() => {
    if (data) setFrames(data.frames)
  }, [data])

  useEffect(() => {
    if (!data) return
    setNodes(buildNodes(shown, frames, { ...data.layout, ...moved }))
    setEdges(buildEdges(data.edges, new Set(shown.map((node) => node.id))))
  }, [data, shown, frames, moved, setNodes, setEdges])

  useEffect(() => {
    if (!saved) return
    const timer = setTimeout(() => setSaved(false), 2000)
    return () => clearTimeout(timer)
  }, [saved])

  const save = useMutation({ mutationFn: () => saveLayout(positions(nodes)), onSuccess: () => setSaved(true) })

  const addFrame = () =>
    setFrames((current) => {
      const next = current.filter((frame) => frame.id.startsWith(LOCAL_FRAME)).length + 1
      return [...current, { id: `${LOCAL_FRAME}${next}`, label: `Frame ${next}`, nodes: [] }]
    })

  const onNodeDragStop: OnNodeDrag<CanvasFlowNode> = (event, node) => {
    const pointer = 'clientX' in event ? event : event.changedTouches[0]
    const dropped = flow.screenToFlowPosition({ x: pointer.clientX, y: pointer.clientY })
    const target = node.type === 'file' ? frameAt(dropped, campaignBoxes(nodes)) : null
    if (target === null || node.parentId === target) {
      setMoved((current) => ({ ...current, [node.id]: node.position }))
      return
    }
    setMoved((current) => Object.fromEntries(Object.entries(current).filter(([id]) => id !== node.id)))
    setFrames((current) =>
      current.map((frame) => ({
        ...frame,
        nodes: frame.id === target ? [...frame.nodes, node.id] : frame.nodes.filter((id) => id !== node.id),
      })),
    )
  }

  const all = data?.nodes ?? []
  const months = [...new Set([...all.map((node) => node.date.slice(0, 7)), ...(month === '' ? [] : [month])])].sort().reverse()
  const kinds = [...new Set([...all.map((node) => node.kind), ...(kind === '' ? [] : [kind])])].sort()

  return (
    <div className="space-y-4" data-testid="canvas-view" data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      <div className="flex flex-wrap items-center gap-2">
        <select className={SELECT} value={month} onChange={(event) => setMonth(event.target.value)} aria-label="date" data-testid="canvas-filter-date">
          <option value="">all dates</option>
          {months.map((value) => (
            <option key={value} value={value}>
              {shortDate(value)}
            </option>
          ))}
        </select>
        <select className={SELECT} value={kind} onChange={(event) => setKind(event.target.value)} aria-label="kind" data-testid="canvas-filter-kind">
          <option value="">all kinds</option>
          {kinds.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select className={SELECT} value={skill} onChange={(event) => setSkill(event.target.value)} aria-label="skill" data-testid="canvas-filter-skill">
          <option value="">all skills</option>
        </select>
        <Input
          className="h-8 w-32 text-xs sm:w-44"
          placeholder="search…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="search"
          data-testid="canvas-search"
        />
        <Button size="sm" onClick={addFrame} data-testid="canvas-add-frame">
          + Frame
        </Button>
        <Button size="sm" onClick={() => flow.fitView({ padding: 0.1 })} data-testid="canvas-fit">
          Fit
        </Button>
        <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()} data-testid="canvas-save-layout">
          {save.isPending ? 'Saving…' : 'Save layout'}
        </Button>
        <span aria-live="polite" className="text-xs text-muted">
          {saved ? 'saved' : null}
        </span>
      </div>

      {save.error && <ErrorBanner error={asApiError(save.error)} testId="canvas-save-error" />}

      {query.error ? (
        <ErrorBanner error={asApiError(query.error)} />
      ) : !data ? (
        <Loading />
      ) : shown.length === 0 ? (
        <Empty>no nodes</Empty>
      ) : (
        <Card className="h-[70vh] min-h-[420px] overflow-hidden p-0 sm:p-0" data-testid="canvas-flow">
          <ReactFlow<CanvasFlowNode, Edge>
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => {
              if (node.type === 'file') setOpen(node.data.node)
            }}
            onNodeDragStop={onNodeDragStop}
            nodesDraggable
            nodesConnectable={false}
            minZoom={0.2}
            fitView
            fitViewOptions={{ padding: 0.1 }}
          >
            <Background color="#E0DCC1" gap={24} />
            <Controls />
            <Panel position="top-right" className="flex flex-col gap-1 rounded-lg border border-line bg-paper/90 px-2 py-1.5 text-[10px] text-muted">
              {LINEAGE.map((entry) => (
                <span key={entry.rel} className="flex items-center gap-1.5">
                  <svg width="28" height="8" aria-hidden="true">
                    <line x1="0" y1="4" x2="28" y2="4" stroke={entry.stroke} strokeWidth={entry.width} strokeDasharray={entry.dash} />
                  </svg>
                  {entry.rel}
                </span>
              ))}
            </Panel>
          </ReactFlow>
        </Card>
      )}

      <p className="text-xs text-muted" data-testid="canvas-footer">
        nodes are files in the media store · edges are lineage: ancestor → draft → build
      </p>

      <Preview node={open} onClose={() => setOpen(null)} />
    </div>
  )
}

export function Canvas() {
  return (
    <ReactFlowProvider>
      <Board />
    </ReactFlowProvider>
  )
}
