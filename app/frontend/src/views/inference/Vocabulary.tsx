import { Section } from '@/components/SectionHeading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { plural, short } from '@/lib/format'

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

export function Readings({ vocabulary }: { vocabulary: Vocabulary }) {
  return (
    <>
      {Object.entries(vocabulary.readings).map(([name, r]) => (
        <Section key={name} title={name}>
          <p className="text-sm text-dbb-muted">
            reads{' '}
            <Mono>
              {r.entity}.{r.input}
            </Mono>{' '}
            · sha <Mono title={r.sha}>{short(r.sha, 12)}</Mono> · {plural(r.fields.length, 'field')}
          </p>
          <p className="mt-1 max-w-prose text-sm text-dbb-muted">{r.description}</p>
          <Table className="mt-3">
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Labels</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.fields.map((f) => (
                <TableRow key={f.name}>
                  <TableCell className="align-top font-mono text-xs text-dbb-charcoal">{f.name}</TableCell>
                  <TableCell className="align-top">
                    <Pill>{f.type}</Pill>
                  </TableCell>
                  <TableCell className="max-w-md align-top">{f.description}</TableCell>
                  <TableCell className="align-top">
                    <dl className="space-y-1">
                      {f.labels.map((g) => (
                        <div key={g.label} className="flex gap-3">
                          <dt className="w-44 shrink-0 font-mono text-xs text-dbb-charcoal">{g.label}</dt>
                          <dd>{g.means}</dd>
                        </div>
                      ))}
                    </dl>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      ))}
    </>
  )
}
