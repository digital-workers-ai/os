import { humanize, labelsOf, meaningOf } from '@/lib/values'
import { text, type ControlProps } from './context'

export function OneOfField({ field, value, onChange, id, label, testId, disabled }: ControlProps) {
  return (
    <select
      id={id}
      aria-label={label}
      value={text(value)}
      onChange={(event) => onChange(event.target.value || null)}
      disabled={disabled}
      className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-2 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 md:text-sm"
      data-testid={testId}
    >
      <option value="">—</option>
      {labelsOf(field).map((option) => (
        <option key={option} value={option} title={meaningOf(field, option) || undefined}>
          {humanize(option)}
        </option>
      ))}
    </select>
  )
}
