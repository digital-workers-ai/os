import type { Cursor, Template, TemplateValues } from '@/api'
import { Control } from '@/components/fields/Control'
import { useForm } from '@/components/fields/context'
import { cn } from '@/lib/utils'
import { humanize, itemKey } from '@/lib/values'

interface Props {
  template: Template
  values: TemplateValues
  cursor: Cursor | null
  onCursor: (cursor: Cursor) => void
  disabled?: boolean
}

export function Checklist({ template, values, cursor, onCursor, disabled }: Props) {
  const { set } = useForm()
  const fields = template.items?.fields ?? []

  return (
    <div className="flex flex-col gap-5">
      {Object.entries(template.sections ?? {}).map(([section, items]) => (
        <section key={section} className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted">{humanize(section)}</h2>
          {items.map((item) => {
            const key = itemKey(section, item)
            const entry = values.items[key] ?? {}
            const current = cursor?.section === section && cursor?.item === item
            return (
              <div
                key={item}
                aria-current={current ? 'true' : undefined}
                onFocus={() => current || onCursor({ section, item })}
                className={cn('flex flex-col gap-2 rounded-lg border bg-paper p-3', current ? 'border-ink' : 'border-line')}
                data-testid={`checklist-${section}-${item}`}
              >
                <span className="text-sm font-medium text-ink">{humanize(item)}</span>
                <div className="flex flex-wrap items-center gap-2 [&>*]:min-w-28 [&>*]:flex-1">
                  {fields.map((field) => (
                    <Control
                      key={field.name}
                      field={field}
                      value={entry[field.name]}
                      onChange={(value) => set(['template', 'items', key, field.name], value)}
                      label={`${humanize(item)}: ${field.name.replace(/_/g, ' ')}`}
                      path={field.name}
                      file={`${section}-${item}-${field.name}`}
                      disabled={disabled}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </section>
      ))}
    </div>
  )
}
