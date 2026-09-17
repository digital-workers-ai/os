import type { AssetVersion } from '@/api'
import { Hint } from '@/components/ui/hint'
import { Mono } from '@/components/ui/mono'
import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const VERSIONS_HINT = 'Every build of this asset, newest first, each with the note that asked for it; version 1 carries the original ask.'

const when = (iso: string) => `${shortDate(iso.slice(0, 10))} ${iso.slice(11, 16)}`

export function Versions({ versions, selected, onSelect }: { versions: AssetVersion[]; selected: number; onSelect: (version: number) => void }) {
  return (
    <section className="flex flex-col gap-2" data-testid="asset-versions">
      <h2 className="border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">
        Versions
        <Hint text={VERSIONS_HINT} />
      </h2>
      <ul className="flex flex-col gap-0.5">
        {versions.map((version) => (
          <li key={version.version}>
            <button
              type="button"
              aria-pressed={version.version === selected}
              onClick={() => onSelect(version.version)}
              className={cn(
                'flex w-full items-baseline gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                version.version === selected ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:bg-black/[0.04]',
              )}
              data-testid="asset-version"
              data-version={version.version}
            >
              <Mono className="shrink-0">v{version.version}</Mono>
              <span className="min-w-0 flex-1 truncate">{version.note}</span>
              <span className="shrink-0 text-[11px] text-muted">{when(version.created_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
