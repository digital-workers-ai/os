import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { asApiError, getAsset, type Asset } from '@/api'
import { Build } from '@/components/assets/Build'
import { Feedback } from '@/components/assets/Feedback'
import { Lineage } from '@/components/assets/Lineage'
import { Preview } from '@/components/assets/Preview'
import { stampLabel } from '@/components/assets/stamp'
import { Versions } from '@/components/assets/Versions'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'

function Detail({ seq, query }: { seq: number; query: UseQueryResult<Asset> }) {
  const [picked, setPicked] = useState<number | null>(null)
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const asset = query.data
  const versions = [...asset.versions].sort((a, b) => b.version - a.version)
  const version = versions.find((entry) => entry.version === picked) ?? versions[0] ?? null

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <Preview seq={seq} version={version} />
        <Versions versions={versions} selected={version?.version ?? null} onSelect={setPicked} />
      </div>
      <div className="space-y-6">
        <Lineage asset={asset} />
        <Build seq={seq} skillRunSeq={asset.skill_run_seq} />
        <Feedback seq={seq} feedback={asset.feedback} />
      </div>
    </div>
  )
}

export function AssetDetail() {
  const seq = Number(useParams().seq)
  const query = useQuery({ queryKey: ['asset', seq], queryFn: () => getAsset(seq) })
  const asset = query.data

  return (
    <div
      className="space-y-6"
      data-testid="asset-detail-view"
      data-seq={seq}
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-line pb-3">
        <Link to="/assets" className="whitespace-nowrap text-sm text-muted hover:text-ink" data-testid="asset-back">
          ◂ Assets
        </Link>
        {asset && (
          <h1 className="min-w-0 text-base font-medium text-ink">
            {asset.name} <span className="text-muted">· {asset.kind} · {asset.status} {stampLabel(asset.created_at)}</span>
          </h1>
        )}
      </div>
      <Detail seq={seq} query={query} />
    </div>
  )
}
