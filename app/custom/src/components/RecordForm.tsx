import type { Cursor, Values } from '@/api'
import { useForm } from '@/components/fields/context'
import { Fields } from '@/components/fields/Fields'
import { Checklist } from '@/components/templates/Checklist'
import { Grid } from '@/components/templates/Grid'
import { templateOf } from '@/lib/values'

export function RecordForm({
  values,
  cursor,
  onCursor,
  disabled,
}: {
  values: Values
  cursor: Cursor | null
  onCursor: (cursor: Cursor) => void
  disabled?: boolean
}) {
  const { app } = useForm()
  const template = app.template
  const shared = { template: template!, values: templateOf(values), cursor, onCursor, disabled }
  return (
    <div className="flex flex-col gap-6">
      <Fields fields={app.fields} values={values} disabled={disabled} />
      {template && (template.kind === 'grid' ? <Grid {...shared} /> : <Checklist {...shared} />)}
    </div>
  )
}
