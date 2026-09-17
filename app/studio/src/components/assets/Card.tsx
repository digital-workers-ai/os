import { FileText, GalleryHorizontalEnd, Image, Mail, MessageSquare, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AssetRow, Kind, Origin, RunStatus } from '@/api'
import { Mono } from '@/components/ui/mono'
import { Pill, type Tone } from '@/components/ui/pill'
import { cn } from '@/lib/utils'

const GLYPHS: Record<Kind, LucideIcon> = {
  post: MessageSquare,
  newsletter: Mail,
  blog: FileText,
  image: Image,
  carousel: GalleryHorizontalEnd,
}

const STATUS_LABEL: Record<RunStatus, string> = { running: 'building', ok: 'ok', held: 'held', failed: 'failed' }

const STATUS_TONE: Record<RunStatus, Tone> = { running: 'unknown', ok: 'ok', held: 'down', failed: 'down' }

export function KindGlyph({ kind, size = 16, className }: { kind: Kind; size?: number; className?: string }) {
  const Glyph = GLYPHS[kind]
  return <Glyph size={size} className={cn('shrink-0 text-muted', className)} aria-label={kind} data-testid="kind-glyph" data-kind={kind} />
}

export function OriginPill({ origin }: { origin: Origin }) {
  return (
    <Pill title={`made by ${origin}`} data-testid="origin-pill">
      {origin}
    </Pill>
  )
}

export function StatusPill({ status }: { status: RunStatus }) {
  return (
    <Pill tone={STATUS_TONE[status]} className={cn(status === 'failed' && 'bg-err/10 text-err')} data-testid="status-pill">
      {STATUS_LABEL[status]}
    </Pill>
  )
}

export function AssetCard({ asset }: { asset: AssetRow }) {
  return (
    <Link
      to={`/assets/${asset.seq}`}
      className="flex flex-col overflow-hidden rounded-xl border border-line bg-paper shadow-sm transition-colors hover:border-muted"
      data-testid="asset-card"
      data-seq={asset.seq}
    >
      <div className="flex aspect-square items-center justify-center overflow-hidden bg-wash">
        {asset.preview ? (
          <img src={asset.preview} alt={asset.name} className="h-full w-full object-cover" data-testid="asset-card-preview" />
        ) : (
          <KindGlyph kind={asset.kind} size={32} />
        )}
      </div>
      <div className="flex flex-col gap-1.5 p-3">
        <div className="truncate text-sm font-medium text-ink" title={asset.name} data-testid="asset-card-name">
          {asset.name}
        </div>
        <div className="text-xs text-muted">{asset.look ?? asset.kind}</div>
        <div className="flex flex-wrap items-center gap-1">
          <OriginPill origin={asset.origin} />
          {asset.status !== 'ok' && <StatusPill status={asset.status} />}
          {asset.version > 1 && (
            <span data-testid="asset-card-version">
              <Mono className="text-muted">v{asset.version}</Mono>
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}
