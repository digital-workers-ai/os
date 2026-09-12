import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, short } from '@/lib/format'

export interface Gloss {
  label: string
  means: string
}

export interface Field {
  name: string
  type: string
  description: string
  labels: Gloss[]
}

export interface Reading {
  entity: string
  input: string
  description: string
  sha: string
  fields: Field[]
}

export interface Vocabulary {
  enabled: boolean
  model: string
  readings: Record<string, Reading>
}

export function Readings({
  vocabulary,
  sticky = false,
  testId,
  selected = null,
}: {
  vocabulary: Vocabulary
  sticky?: boolean
  testId?: string
  selected?: string | null
}) {
  const readings = Object.entries(vocabulary.readings)
  return (
    <Table className="table-fixed" wrapperClassName={sticky ? 'overflow-x-visible' : undefined} data-testid={testId}>
      <TableHeader className={sticky ? STICKY_HEAD : undefined}>
        <TableRow>
          <TableHead className="w-64" hint="Questions the model answers about one text field">Reading ({num(readings.length)})</TableHead>
          <TableHead className="w-32" hint="Digest of the questions when they were written">Vocabulary</TableHead>
          <TableHead className="w-32" hint="One question the model answers">Field</TableHead>
          <TableHead className="w-24" hint="Whether one answer or several may be chosen">Type</TableHead>
          <TableHead className="w-64" hint="What the question means and how to answer it">Description</TableHead>
          <TableHead hint="The answers the model may choose, with meanings">Labels</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {readings.flatMap(([name, r]) =>
          r.fields.map((f, i) => (
            <TableRow
              key={`${name}|${f.name}`}
              data-name={name}
              data-state={name === selected ? 'selected' : undefined}
              aria-selected={name === selected}
            >
              {i === 0 && (
                <>
                  <TableCell rowSpan={r.fields.length} className="align-top">
                    <span className="block font-medium text-ink">{name}</span>
                    <Mono className="block">
                      {r.entity}.{r.input}
                    </Mono>
                    <span className="mt-1 block">{r.description}</span>
                  </TableCell>
                  <TableCell rowSpan={r.fields.length} className="align-top">
                    <Mono title={r.sha}>{short(r.sha, 12)}</Mono>
                  </TableCell>
                </>
              )}
              <TableCell className="align-top font-mono text-xs text-ink">{f.name}</TableCell>
              <TableCell className="align-top">
                <Pill>{f.type}</Pill>
              </TableCell>
              <TableCell className="align-top">{f.description}</TableCell>
              <TableCell className="align-top">
                <dl className="space-y-2">
                  {f.labels.map((g) => (
                    <div key={g.label}>
                      <dt className="font-mono text-xs text-ink">{g.label}</dt>
                      <dd>{g.means}</dd>
                    </div>
                  ))}
                </dl>
              </TableCell>
            </TableRow>
          )),
        )}
      </TableBody>
    </Table>
  )
}
