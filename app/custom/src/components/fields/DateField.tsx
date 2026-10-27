import { Input } from '@/components/ui/input'
import { text, type ControlProps } from './context'

export function DateField({ value, onChange, id, label, testId, disabled }: ControlProps) {
  return (
    <Input
      id={id}
      type="date"
      aria-label={label}
      value={text(value)}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      data-testid={testId}
    />
  )
}
