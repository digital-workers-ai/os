import type { AssetVersion } from '@/api'
import { Section } from '@/components/assets/Section'
import { stampLabel } from '@/components/assets/stamp'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { cn } from '@/lib/utils'

export function Versions({
  versions,
  selected,
  onSelect,
}: {
  versions: AssetVersion[]
  selected: number | null
  onSelect: (version: number) => void
}) {
  const newest = versions[0]?.version ?? null
  return (
    <Section title="Versions" testId="asset-versions">
      {versions.length === 0 ? (
        <Empty>no version recorded</Empty>
      ) : (
        <ul className="space-y-1">
          {versions.map((version) => (
            <li key={version.version}>
              <button
                type="button"
                aria-pressed={version.version === selected}
                onClick={() => onSelect(version.version)}
                className={cn(
                  'w-full rounded-md px-2 py-1.5 text-left transition-colors',
                  version.version === selected ? 'bg-wash' : 'hover:bg-wash/60',
                )}
                data-testid="asset-version"
                data-version={version.version}
              >
                <span className="flex flex-wrap items-baseline gap-x-2 text-sm">
                  <Mono className="text-ink">v{version.version}</Mono>
                  <span className="text-muted">{stampLabel(version.created_at)}</span>
                  {version.version === newest && <span className="text-muted">(this)</span>}
                </span>
                {version.note && <span className="mt-0.5 block text-xs text-muted">rebuilt: “{version.note}”</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}
