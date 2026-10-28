import type { Cursor, Field, Template, TemplateValues, Values } from '@/api'
import { Control } from '@/components/fields/Control'
import { text, useForm } from '@/components/fields/context'
import { cn } from '@/lib/utils'
import { cellKey, humanize } from '@/lib/values'

interface Props {
  template: Template
  values: TemplateValues
  cursor: Cursor | null
  onCursor: (cursor: Cursor) => void
  disabled?: boolean
}

function Editor({
  title,
  fields,
  entry,
  onChange,
  file,
  disabled,
}: {
  title: string
  fields: Field[]
  entry: Values
  onChange: (name: string, value: unknown) => void
  file: string
  disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <span className="w-full text-sm font-medium text-ink">{title}</span>
      {fields.map((field) => (
        <label key={field.name} className="flex min-w-24 flex-1 flex-col gap-1 text-xs text-muted">
          {humanize(field.name)}
          <Control
            field={field}
            value={entry[field.name]}
            onChange={(value) => onChange(field.name, value)}
            path={field.name}
            file={`${file}-${field.name}`}
            disabled={disabled}
          />
        </label>
      ))}
    </div>
  )
}

export function Grid({ template, values, cursor, onCursor, disabled }: Props) {
  const { set } = useForm()
  const rows = template.rows!
  const columns = template.columns!
  const cells = template.cells!
  const [main, ...marks] = cells.fields ?? []
  const row = cursor?.row === undefined ? null : String(cursor.row)
  const column = cursor?.column === undefined ? null : String(cursor.column)
  const rowName = humanize(rows.name ?? 'row')
  const columnName = humanize(columns.name ?? 'column')

  return (
    <div className="flex flex-col gap-3">
      {row !== null && (
        <div className="flex flex-col gap-3 rounded-lg border border-line bg-paper p-3">
          <Editor
            title={`${rowName} ${row}`}
            fields={rows.fields ?? []}
            entry={values.rows[row] ?? {}}
            onChange={(name, value) => set(['template', 'rows', row, name], value)}
            file={`${rows.name}-${row}`}
            disabled={disabled}
          />
          {column !== null && (
            <Editor
              title={`${columnName} ${column}`}
              fields={cells.fields ?? []}
              entry={values.cells[cellKey(row, column)] ?? {}}
              onChange={(name, value) => set(['template', 'cells', cellKey(row, column), name], value)}
              file={`${rows.name}-${row}-${column}`}
              disabled={disabled}
            />
          )}
        </div>
      )}
      <table className="w-full table-fixed border-collapse text-center text-sm">
        <thead>
          <tr>
            <th className="w-12 pb-1 text-left text-xs font-medium text-muted">{rowName}</th>
            {(columns.values ?? []).map((name) => (
              <th key={name} className="pb-1 text-xs font-medium text-muted">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(rows.values ?? []).map((rowValue) => (
            <tr key={rowValue}>
              <th scope="row" className="text-left text-xs font-medium tabular-nums text-muted">
                {rowValue}
              </th>
              {(columns.values ?? []).map((columnValue) => {
                const entry = values.cells[cellKey(rowValue, columnValue)] ?? {}
                const current = rowValue === row && columnValue === column
                return (
                  <td key={columnValue} className="p-0.5">
                    <button
                      type="button"
                      title={`${rowName} ${rowValue}, ${columnName} ${columnValue}`}
                      aria-current={current ? 'true' : undefined}
                      onClick={() => onCursor({ row: rowValue, column: columnValue })}
                      className={cn(
                        'flex h-8 w-full items-center justify-center rounded-md border bg-paper tabular-nums text-ink',
                        current ? 'border-ink ring-1 ring-ink' : 'border-line',
                      )}
                      data-testid={`grid-cell-${rowValue}-${columnValue}`}
                    >
                      {main && text(entry[main.name])}
                      {marks.map(
                        (mark) =>
                          entry[mark.name] !== null &&
                          entry[mark.name] !== undefined && (
                            <sup key={mark.name} className="ml-0.5 text-[10px] text-brand">
                              {text(entry[mark.name]).charAt(0)}
                            </sup>
                          ),
                      )}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
