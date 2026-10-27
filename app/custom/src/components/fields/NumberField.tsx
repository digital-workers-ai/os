import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { text, type ControlProps } from './context'

const DECIMAL = /^-?\d*\.?\d*$/

export function NumberField({ field, value, onChange, id, label, testId, disabled }: ControlProps) {
  const money = field.type === 'money'
  const unit = field.unit ?? (money ? 'USD' : null)
  return (
    <div className="relative flex items-center">
      <Input
        id={id}
        aria-label={label}
        inputMode="decimal"
        value={money && typeof value === 'number' ? value.toFixed(2) : text(value)}
        onChange={(event) => {
          const next = event.target.value.replace(',', '.')
          if (DECIMAL.test(next)) onChange(next)
        }}
        onBlur={() => {
          const typed = parseFloat(text(value))
          if (money && typeof value === 'string' && Number.isFinite(typed)) onChange(typed)
        }}
        disabled={disabled}
        className={cn(unit && 'pr-12')}
        data-testid={testId}
      />
      {unit && <span className="pointer-events-none absolute right-3 text-xs text-muted">{unit}</span>}
    </div>
  )
}
