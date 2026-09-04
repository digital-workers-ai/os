import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { num } from '@/lib/format'

export const ALL = '*'

export function Filter({
  value,
  onChange,
  all,
  options,
}: {
  value: string
  onChange: (v: string) => void
  all: string
  options: [string, number][]
}) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? '' : v)}>
      <SelectTrigger className="h-6 w-44 font-normal">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{all}</SelectItem>
        {options.map(([name, n]) => (
          <SelectItem key={name} value={name}>
            {name} ({num(n)})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
