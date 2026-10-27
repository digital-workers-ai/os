import { humanize, labelsOf, meaningOf } from '@/lib/values'
import { cn } from '@/lib/utils'
import type { ControlProps } from './context'

export function ManyOfField({ field, value, onChange, label, testId, disabled }: ControlProps) {
  const chosen = Array.isArray(value) ? (value as string[]) : []
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2" data-testid={testId}>
      {labelsOf(field).map((option) => {
        const on = chosen.includes(option)
        return (
          <label
            key={option}
            title={meaningOf(field, option) || undefined}
            className={cn(
              'inline-flex cursor-pointer items-center rounded-full border border-input px-3 py-1 text-sm focus-within:ring-1 focus-within:ring-ring',
              on ? 'border-ink bg-ink text-paper' : 'bg-paper text-ink',
            )}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={on}
              disabled={disabled}
              onChange={() => onChange(on ? chosen.filter((item) => item !== option) : [...chosen, option])}
            />
            {humanize(option)}
          </label>
        )
      })}
    </div>
  )
}
