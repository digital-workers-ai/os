import { Link } from 'react-router-dom'
import type { AssetRow } from '@/api'
import { kindGlyph, mcpTool } from '@/components/assets/kinds'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'

export function AssetCard({ row }: { row: AssetRow }) {
  const built = row.status === 'built'
  return (
    <Link
      to={`/assets/${row.seq}`}
      className="block rounded-xl border border-line bg-paper p-3 transition-colors hover:border-muted"
      data-testid="asset-card"
      data-seq={row.seq}
      data-kind={row.kind}
    >
      {row.preview ? (
        <img src={row.preview} alt="" className="mb-2 h-24 w-full rounded-md border border-line object-cover" />
      ) : (
        <div className="mb-2 flex h-24 w-full items-center justify-center rounded-md border border-dashed border-line text-lg text-muted">
          {kindGlyph(row.kind)}
        </div>
      )}
      <div className="flex items-baseline gap-2">
        <span className="shrink-0 text-xs text-muted">{kindGlyph(row.kind)}</span>
        <span className="min-w-0 flex-1 truncate font-medium text-ink" title={row.name}>
          {row.name}
        </span>
      </div>
      <p className="mt-0.5 truncate text-xs text-muted">{row.look ?? row.kind}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Pill tone={built ? 'ok' : 'unknown'} title={built ? undefined : 'the skill run has not finished yet'}>
          {built ? 'built' : 'building'}
        </Pill>
        {row.origin === 'chat' && <Pill>from chat</Pill>}
      </div>
      <Mono className="mt-2 block text-muted">{row.proposal_seq === null ? mcpTool(row.kind) : `#${row.proposal_seq}`}</Mono>
    </Link>
  )
}
