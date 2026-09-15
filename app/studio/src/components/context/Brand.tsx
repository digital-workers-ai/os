import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getBrand, getBrandFile, type BrandResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

type BrandFileBody = Awaited<ReturnType<typeof getBrandFile>>

const HEADING = 'mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted'

function FileList({
  query,
  selected,
  onSelect,
}: {
  query: UseQueryResult<BrandResponse>
  selected: string | null
  onSelect: (name: string) => void
}) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const files = query.data.files
  if (files.length === 0) return <Empty>definitions/brand/ is empty</Empty>
  const pending = files.filter((file) => file.pending_pr).length
  return (
    <div className="space-y-0.5">
      {files.map((file) => (
        <button
          key={file.name}
          type="button"
          aria-pressed={file.name === selected}
          onClick={() => onSelect(file.name)}
          className={cn(
            'flex w-full items-baseline gap-2 rounded-md px-2 py-1 text-left text-sm text-ink transition-colors hover:bg-wash',
            file.name === selected && 'bg-wash font-medium',
          )}
          data-testid="brand-file"
          data-name={file.name}
        >
          {file.pending_pr ? (
            <span className="text-brand" title="pending PR" data-testid="brand-pending">
              ✎
            </span>
          ) : (
            <span className="text-muted">●</span>
          )}
          <span className="min-w-0 flex-1 truncate">{file.name}</span>
        </button>
      ))}
      {pending > 0 && (
        <p className="px-2 pt-2 text-xs text-muted">
          ✎ {num(pending)} pending PR
        </p>
      )}
    </div>
  )
}

function FileBody({ selected, query }: { selected: string | null; query: UseQueryResult<BrandFileBody> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (selected === null) return <Empty>no file selected</Empty>
  if (!query.data) return <Loading />
  const file = query.data
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
        <h3 className="min-w-0 text-sm font-medium text-ink">{file.title}</h3>
        <span className="text-xs text-muted">{shortDate(file.updated.slice(0, 10))}</span>
      </div>
      {file.body === '' ? (
        <Empty>this file has no body yet</Empty>
      ) : (
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink" data-testid="brand-body">
          {file.body}
        </p>
      )}
      <p className="mt-3 text-sm text-muted" data-testid="brand-used-by">
        used by: {file.used_by.length === 0 ? '—' : file.used_by.join(', ')}
      </p>
      <p className="text-sm text-muted" data-testid="brand-reads">
        read by skill runs {num(file.reads)}×
      </p>
    </div>
  )
}

export function BrandPanel() {
  const files = useQuery({ queryKey: ['brand'], queryFn: getBrand })
  const [picked, setPicked] = useState<string | null>(null)
  const selected = picked ?? files.data?.files[0]?.name ?? null
  const file = useQuery({
    queryKey: ['brand-file', selected],
    queryFn: () => getBrandFile(selected as string),
    enabled: selected !== null,
  })
  return (
    <Card
      className="p-4 sm:p-5"
      data-testid="brand-panel"
      data-state={files.isPending ? 'loading' : files.error ? 'error' : 'ready'}
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]">
        <div>
          <h2 className={HEADING}>definitions/brand/</h2>
          <FileList query={files} selected={selected} onSelect={setPicked} />
        </div>
        <FileBody selected={selected} query={file} />
      </div>
    </Card>
  )
}
