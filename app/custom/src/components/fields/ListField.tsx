import { Plus, X } from 'lucide-react'
import type { Values } from '@/api'
import { Button } from '@/components/ui/button'
import { humanize } from '@/lib/values'
import { useForm, type ControlProps } from './context'
import { FieldRow } from './Fields'

export function ListField({ field, value, onChange, testId, disabled }: ControlProps) {
  const { set } = useForm()
  const rows = Array.isArray(value) ? (value as Values[]) : []

  return (
    <div className="flex flex-col gap-3" data-testid={testId}>
      {rows.map((row, index) => (
        <div key={index} className="flex flex-col gap-3 rounded-lg border border-line bg-paper p-3">
          <div className="flex items-center">
            <span className="text-xs font-medium text-muted">
              {humanize(field.name)} {index + 1}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto size-7"
              disabled={disabled}
              onClick={() => onChange(rows.filter((_, at) => at !== index))}
              aria-label={`Remove ${field.name.replace(/_/g, ' ')} ${index + 1}`}
            >
              <X aria-hidden />
            </Button>
          </div>
          {field.fields.map((sub) => (
            <FieldRow
              key={sub.name}
              field={sub}
              value={row[sub.name]}
              onChange={(next) => set([field.name, index, sub.name], next)}
              path={`${field.name}.${sub.name}`}
              file={`${field.name}-${index}-${sub.name}`}
              testId={`field-${field.name}-${index}-${sub.name}`}
              disabled={disabled}
            />
          ))}
        </div>
      ))}
      <Button size="sm" className="self-start" disabled={disabled} onClick={() => onChange([...rows, {}])}>
        <Plus aria-hidden />
        Add item
      </Button>
    </div>
  )
}
