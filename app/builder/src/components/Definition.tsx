import type { ReactNode } from 'react'
import type { AppDefinition, Field, Part, Template } from '@/api'
import { Mono } from '@/components/ui/mono'
import { Pill, Pills } from '@/components/ui/pill'
import { extraCode } from '@/lib/apps'

const notes = (field: Field) => [
  ...(field.unit ? [`in ${field.unit}`] : []),
  ...(field.entity ? [`looks up ${field.entity} by ${field.by}`] : []),
  ...(field.from_scan ? ['from a scan'] : []),
  ...(field.history ? ['with its history'] : []),
  ...(field.by_script ? ['filled by the script'] : []),
  ...(field.file ? [`drawn by ${field.file}`] : []),
  ...(field.lands_as ? [`each row saves as ${field.lands_as}`] : []),
]

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="contents">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

export function Facts({ app }: { app: AppDefinition }) {
  const code = extraCode(app)
  return (
    <dl className="grid grid-cols-[auto_1fr] items-start gap-x-6 gap-y-2 text-sm" data-testid="app-facts">
      <Fact label="Input">
        <Pills items={app.input} />
      </Fact>
      <Fact label="Saves as">
        <Pill>{app.lands_as}</Pill>
      </Fact>
      <Fact label="Roles">
        <Pills items={app.roles} />
      </Fact>
      <Fact label="Extra code">{code.length > 0 ? <Mono>{code.join(', ')}</Mono> : '—'}</Fact>
    </dl>
  )
}

export function Fields({ fields, path = '' }: { fields: Field[]; path?: string }) {
  return (
    <ul className="flex flex-col divide-y divide-line/60">
      {fields.map((field) => (
        <li key={field.name} className="flex flex-col gap-1.5 py-2" data-testid="app-field" data-name={`${path}${field.name}`}>
          <span className="flex flex-wrap items-center gap-2">
            <Mono className="text-sm text-ink">{field.name}</Mono>
            <Pill>{field.type}</Pill>
            {notes(field).map((note) => (
              <span key={note} className="text-xs text-muted">
                {note}
              </span>
            ))}
          </span>
          {field.description && <span className="text-xs text-muted">{field.description}</span>}
          {field.labels.length > 0 && (
            <ul className="flex flex-col gap-0.5 text-xs">
              {field.labels.map(([label, meaning]) => (
                <li key={label}>
                  <Mono className="text-ink">{label}</Mono>
                  {meaning && <span className="text-muted"> — {meaning}</span>}
                </li>
              ))}
            </ul>
          )}
          {field.fields.length > 0 && (
            <div className="ml-1 border-l border-line pl-3">
              <Fields fields={field.fields} path={`${path}${field.name}.`} />
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

function PartBlock({ label, part, path, children }: { label: string; part: Part; path: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
      {part.values && <span className="text-xs text-muted">{part.values.join(', ')}</span>}
      {part.lands_as && <span className="text-xs text-muted">each saves as {part.lands_as}</span>}
      {part.fields && <Fields fields={part.fields} path={path} />}
    </div>
  )
}

export function TemplateParts({ template }: { template: Template }) {
  return (
    <div className="flex flex-col gap-4" data-testid="app-template" data-kind={template.kind}>
      {template.kind === 'grid' ? (
        <>
          <PartBlock label={`Rows: ${template.rows!.name}`} part={template.rows!} path="rows." />
          <PartBlock label={`Columns: ${template.columns!.name}`} part={template.columns!} path="columns." />
          <PartBlock label={`Cells: one per ${template.rows!.name} and ${template.columns!.name}`} part={template.cells!} path="cells." />
        </>
      ) : (
        <PartBlock label="Items" part={template.items!} path="items.">
          <ul className="flex flex-col gap-1 text-xs">
            {Object.entries(template.sections!).map(([section, items]) => (
              <li key={section}>
                <Mono className="text-ink">{section}</Mono>
                <span className="text-muted">: {items.join(', ')}</span>
              </li>
            ))}
          </ul>
        </PartBlock>
      )}
    </div>
  )
}
