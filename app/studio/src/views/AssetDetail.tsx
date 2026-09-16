import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { asApiError, getAsset, type AssetVersion } from '@/api'
import { OriginPill, StatusPill } from '@/components/assets/Card'
import { EditChat } from '@/components/assets/EditChat'
import { Feedback } from '@/components/assets/Feedback'
import { Lineage } from '@/components/assets/Lineage'
import { Preview } from '@/components/assets/Preview'
import { Versions } from '@/components/assets/Versions'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'

export function AssetDetail() {
  const { seq } = useParams()
  const id = Number(seq)
  const asset = useQuery({ queryKey: ['asset', id], queryFn: () => getAsset(id) })
  const [picked, setPicked] = useState<number | null>(null)
  const state = asset.isPending ? 'loading' : asset.error ? 'error' : 'ready'
  const data = asset.data
  const versions = data ? [...data.versions].sort((a, b) => b.version - a.version) : []
  const selected: AssetVersion | undefined = versions.find((version) => version.version === picked) ?? versions[0]

  return (
    <div className="flex flex-col gap-5" data-testid="asset-detail-view" data-state={state} data-seq={id}>
      <Link to="/assets" className="inline-flex items-center gap-1 self-start text-sm text-muted hover:text-ink" data-testid="asset-back">
        <ArrowLeft size={14} /> Assets
      </Link>
      {asset.error ? (
        <ErrorBanner error={asApiError(asset.error)} />
      ) : !data ? (
        <Loading />
      ) : (
        <>
          <header className="flex flex-wrap items-center gap-2" data-testid="asset-header">
            <h1 className="text-xl text-ink" data-testid="asset-name">
              {data.name}
            </h1>
            <span className="text-sm text-muted" data-testid="asset-meta">
              {[data.kind, data.look, data.ratio].filter(Boolean).join(' · ')}
            </span>
            <OriginPill origin={data.origin} />
            <StatusPill status={data.status} />
          </header>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="flex min-w-0 flex-col gap-5">
              {selected ? <Preview version={selected} /> : <Empty testId="asset-versions-empty">no versions yet</Empty>}
              <Versions versions={versions} selected={selected?.version ?? 0} onSelect={setPicked} />
            </div>
            <div className="flex min-w-0 flex-col gap-5">
              <Lineage asset={data} version={selected?.version ?? data.version} />
              <EditChat asset={data} onVersion={() => setPicked(null)} />
              <Feedback asset={data} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
