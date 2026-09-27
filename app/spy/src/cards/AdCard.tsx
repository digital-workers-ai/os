import { useState } from 'react'
import { Play } from 'lucide-react'
import type { Ad } from '@/api'
import { Card } from '@/components/ui/card'
import { Pill } from '@/components/ui/pill'
import { platformLabel } from '@/lib/engines'
import { host, shortDate } from '@/lib/format'

const degenerate = ({ naturalWidth, naturalHeight }: HTMLImageElement) => naturalWidth <= 1 || naturalHeight <= 1

function Preview({ ad }: { ad: Ad }) {
  const [broken, setBroken] = useState(false)
  if (!ad.preview || broken) {
    return (
      <div className="flex h-40 items-center justify-center bg-wash">
        <Pill tone="unknown">{ad.category || 'ad'}</Pill>
      </div>
    )
  }
  return (
    <img
      src={ad.preview}
      alt={ad.name ?? 'ad preview'}
      className="h-40 w-full bg-wash object-contain"
      onError={() => setBroken(true)}
      onLoad={(event) => setBroken(degenerate(event.currentTarget))}
    />
  )
}

export function AdCard({ ad }: { ad: Ad }) {
  return (
    <Card className="flex flex-col overflow-hidden p-0 sm:p-0" data-testid="ad-card">
      <Preview ad={ad} />
      <div className="flex flex-1 flex-col gap-2 p-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <Pill>{platformLabel(ad.platform)}</Pill>
          <div className="flex items-center gap-3">
            {ad.media && (
              <a data-testid="ad-media" href={ad.media} target="_blank" rel="noreferrer" aria-label="play" className="text-muted hover:text-ink">
                <Play size={14} />
              </a>
            )}
            {ad.url && (
              <a href={ad.url} target="_blank" rel="noreferrer" className="text-xs text-muted underline-offset-4 hover:text-ink hover:underline">
                View
              </a>
            )}
          </div>
        </div>
        {ad.name ? (
          <p className="line-clamp-2 text-ink" title={ad.name}>
            {ad.name}
          </p>
        ) : (
          <p className="text-muted">text not read yet</p>
        )}
        {ad.landing_url && (
          <a
            data-testid="ad-landing"
            href={ad.landing_url}
            target="_blank"
            rel="noreferrer"
            className="truncate text-xs text-muted underline-offset-4 hover:text-ink hover:underline"
          >
            Lands {host(ad.landing_url)}
          </a>
        )}
        <p className="mt-auto text-xs text-muted">
          first {shortDate(ad.first_seen.slice(0, 10))} · last {shortDate(ad.last_seen.slice(0, 10))}
        </p>
      </div>
    </Card>
  )
}
