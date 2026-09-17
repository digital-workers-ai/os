import { useStore, type NodeProps, type ReactFlowState } from '@xyflow/react'
import { FileText } from 'lucide-react'
import type { Origin, RunStatus } from '@/api'
import { Pill, type Tone } from '@/components/ui/pill'
import { CARD, COLUMN_WIDTH, HEADER_HEIGHT, isPicture, KIND_COLORS, type AssetFlowNode, type DayFlowNode } from '@/lib/canvas'
import { shortDate } from '@/lib/format'

const ORIGIN_TONE: Record<Origin, Tone> = { chat: 'neutral', marketer: 'ok', mcp: 'unknown' }

const STATUS_TONE: Record<Exclude<RunStatus, 'ok'>, Tone> = { running: 'unknown', held: 'down', failed: 'down' }

const selectDots = (state: ReactFlowState) => state.transform[2] < 0.3

export function AssetNode({ data }: NodeProps<AssetFlowNode>) {
  const dots = useStore(selectDots)
  const { node } = data
  const picture = isPicture(node) ? node.url : null
  return (
    <div
      className="flex items-center justify-center"
      style={{ width: CARD.width, height: CARD.height }}
      data-testid="canvas-node"
      data-seq={node.asset_seq}
      data-kind={node.kind}
      data-zoom={dots ? 'dot' : 'card'}
    >
      {dots ? (
        <div className="h-12 w-12 rounded-full" style={{ background: KIND_COLORS[node.kind] }} title={node.label} />
      ) : (
        <div className="flex h-full w-full flex-col overflow-hidden rounded-lg border border-line bg-paper shadow-sm">
          {picture ? (
            <img src={picture} alt={node.label} className="h-[124px] w-full object-cover" draggable={false} />
          ) : (
            <div className="flex h-[124px] w-full items-center justify-center bg-wash">
              <FileText size={28} className="text-muted" />
            </div>
          )}
          <div className="flex flex-1 flex-col justify-center gap-1 px-2 py-1.5">
            <span className="truncate text-xs text-ink" title={node.label}>
              {node.label}
            </span>
            <div className="flex items-center gap-1">
              <Pill tone={ORIGIN_TONE[node.origin]} data-testid="canvas-node-origin">
                {node.origin}
              </Pill>
              {node.status !== 'ok' && (
                <Pill tone={STATUS_TONE[node.status]} data-testid="canvas-node-status">
                  {node.status}
                </Pill>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function DayNode({ data }: NodeProps<DayFlowNode>) {
  return (
    <div
      className="pointer-events-none flex items-baseline gap-2"
      style={{ width: COLUMN_WIDTH, height: HEADER_HEIGHT }}
      data-testid="canvas-day"
      data-date={data.date}
    >
      <span className="text-sm font-medium text-ink">{shortDate(data.date)}</span>
      <span className="text-xs text-muted">{data.count}</span>
    </div>
  )
}

export const nodeTypes = { asset: AssetNode, day: DayNode }
