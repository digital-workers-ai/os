import { useId } from 'react'
import type { Field, Values } from '@/api'
import { humanize } from '@/lib/values'
import { useForm, type ControlProps } from './context'
import { Control } from './Control'

const LABELLED = new Set(['text', 'number', 'money', 'date', 'one_of', 'lookup'])

export function FieldRow(props: ControlProps) {
  const id = useId()
  const { field } = props
  const name = humanize(field.name)
  const labelled = LABELLED.has(field.type)
  return (
    <div className="flex flex-col gap-1.5">
      {labelled ? (
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {name}
        </label>
      ) : (
        <span className="text-sm font-medium text-ink">{name}</span>
      )}
      {field.description && <p className="-mt-1 text-xs text-muted">{field.description}</p>}
      <Control
        {...props}
        id={labelled ? id : undefined}
        label={labelled ? undefined : name}
        disabled={props.disabled || field.by_script}
      />
      {field.by_script && <p className="text-xs text-muted">Worked out when the record is saved.</p>}
    </div>
  )
}

export function Fields({ fields, values, disabled }: { fields: Field[]; values: Values; disabled?: boolean }) {
  const { set } = useForm()
  return (
    <div className="flex flex-col gap-4">
      {fields.map((field) => (
        <FieldRow
          key={field.name}
          field={field}
          value={values[field.name]}
          onChange={(value) => set([field.name], value)}
          path={field.name}
          file={field.name}
          testId={`field-${field.name}`}
          disabled={disabled}
        />
      ))}
    </div>
  )
}
