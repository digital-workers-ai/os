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

export function Readings({ vocabulary, sticky = false }: { vocabulary: Vocabulary; sticky?: boolean }) {
  const readings = Object.entries(vocabulary.readings)
  return (
    <Table className="table-fixed" wrapperClassName={sticky ? 'overflow-x-visible' : undefined}>
      <TableHeader className={sticky ? STICKY_HEAD : undefined}>
        <TableRow>
          <TableHead className="w-64">Reading ({num(readings.length)})</TableHead>
          <TableHead className="w-32">Vocabulary</TableHead>
          <TableHead className="w-32">Field</TableHead>
          <TableHead className="w-24">Type</TableHead>
          <TableHead className="w-64">Description</TableHead>
          <TableHead>Labels</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {readings.flatMap(([name, r]) =>
          r.fields.map((f, i) => (
            <TableRow key={`${name}|${f.name}`}>
              {i === 0 && (
                <>
                  <TableCell rowSpan={r.fields.length} className="align-top">
                    <span className="block font-medium text-dbb-charcoal">{name}</span>
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
              <TableCell className="align-top font-mono text-xs text-dbb-charcoal">{f.name}</TableCell>
              <TableCell className="align-top">
                <Pill>{f.type}</Pill>
              </TableCell>
              <TableCell className="align-top">{f.description}</TableCell>
              <TableCell className="align-top">
                <dl className="space-y-2">
                  {f.labels.map((g) => (
                    <div key={g.label}>
                      <dt className="font-mono text-xs text-dbb-charcoal">{g.label}</dt>
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
