import type { AssetFilters, Kind, LookRow, Origin } from '@/api'
import { Input } from '@/components/ui/input'

const KINDS: Kind[] = ['post', 'newsletter', 'blog', 'image', 'carousel']

const ORIGINS: Origin[] = ['chat', 'marketer', 'mcp']

const SELECT =
  'h-9 rounded-md border border-input bg-transparent px-2 text-sm text-ink shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'

function Select({
  value,
  options,
  label,
  testId,
  onChange,
}: {
  value: string
  options: string[]
  label: string
  testId: string
  onChange: (value: string) => void
}) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} aria-label={label} className={SELECT} data-testid={testId}>
      <option value="">{label}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  )
}

export function Filters({ value, looks, onChange }: { value: AssetFilters; looks: LookRow[]; onChange: (value: AssetFilters) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="assets-filters">
      <Select
        value={value.kind ?? ''}
        options={KINDS}
        label="any kind"
        testId="assets-filter-kind"
        onChange={(kind) => onChange({ ...value, kind: kind ? (kind as Kind) : undefined })}
      />
      <Select
        value={value.look ?? ''}
        options={looks.map((look) => look.name)}
        label="any look"
        testId="assets-filter-look"
        onChange={(look) => onChange({ ...value, look: look || undefined })}
      />
      <Select
        value={value.origin ?? ''}
        options={ORIGINS}
        label="any origin"
        testId="assets-filter-origin"
        onChange={(origin) => onChange({ ...value, origin: origin ? (origin as Origin) : undefined })}
      />
      <Input
        type="search"
        value={value.q ?? ''}
        onChange={(event) => onChange({ ...value, q: event.target.value || undefined })}
        placeholder="search"
        aria-label="search"
        className="w-56"
        data-testid="assets-search"
      />
    </div>
  )
}
