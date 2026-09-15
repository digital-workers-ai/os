import { useQuery } from '@tanstack/react-query'
import { getLooks } from '@/api'
import { KINDS } from '@/components/assets/kinds'
import { Input } from '@/components/ui/input'

export interface AssetFilters {
  kind: string
  look: string
  origin: string
  q: string
}

export const NO_FILTERS: AssetFilters = { kind: '', look: '', origin: '', q: '' }

const SELECT = 'h-8 max-w-full rounded-md border border-line bg-paper px-2 text-xs text-ink'

export function Filters({ filters, onChange }: { filters: AssetFilters; onChange: (next: AssetFilters) => void }) {
  const looks = useQuery({ queryKey: ['looks'], queryFn: getLooks })
  const names = looks.data?.looks.map((look) => look.name) ?? []

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={filters.kind}
        onChange={(event) => onChange({ ...filters, kind: event.target.value })}
        className={SELECT}
        aria-label="kind"
        data-testid="assets-filter-kind"
      >
        <option value="">all kinds</option>
        {KINDS.map((kind) => (
          <option key={kind} value={kind}>
            {kind}
          </option>
        ))}
      </select>
      <select
        value={filters.look}
        onChange={(event) => onChange({ ...filters, look: event.target.value })}
        className={SELECT}
        aria-label="look"
        data-testid="assets-filter-look"
      >
        <option value="">all looks</option>
        {names.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      <select
        value=""
        disabled
        className={SELECT}
        aria-label="skill"
        title="the assets API returns no skill per row yet"
        data-testid="assets-filter-skill"
      >
        <option value="">all skills</option>
      </select>
      <select
        value={filters.origin}
        onChange={(event) => onChange({ ...filters, origin: event.target.value })}
        className={SELECT}
        aria-label="source"
        data-testid="assets-filter-origin"
      >
        <option value="">all sources</option>
        <option value="proposal">proposal</option>
        <option value="chat">chat</option>
      </select>
      <Input
        value={filters.q}
        onChange={(event) => onChange({ ...filters, q: event.target.value })}
        placeholder="search…"
        aria-label="search assets"
        className="h-8 w-full text-xs sm:w-48"
        data-testid="assets-search"
      />
    </div>
  )
}
