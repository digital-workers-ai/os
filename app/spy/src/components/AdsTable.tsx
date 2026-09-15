import type { UseQueryResult } from '@tanstack/react-query'
import type { Ad, AdsResponse } from '@/api'
import { Synced } from '@/components/Synced'
import { Cell, DateCell, Head, LinkCell, Row, Table, TextCell, Th } from '@/components/Table'
import { num, shortDate } from '@/lib/format'

const count = ({ total, running }: AdsResponse) => `${num(total)} ads · ${num(running)} running`

function StatusCell({ row }: { row: Ad }) {
  if (row.days_running === null) return <Cell className="text-muted">—</Cell>
  if (row.running) {
    return (
      <Cell className="whitespace-nowrap tabular-nums text-ink">
        {num(row.days_running)} d <span className="text-ok">●</span>
      </Cell>
    )
  }
  return <Cell className="whitespace-nowrap tabular-nums text-muted">→ {shortDate(row.last_seen)}</Cell>
}

export function AdsTable({ slug, query, format = false }: { slug: string; query: UseQueryResult<AdsResponse>; format?: boolean }) {
  return (
    <Synced slug={slug} query={query} count={count} empty={(data) => data.rows.length === 0}>
      {(data) => (
        <Table>
          <Head>
            <Th>competitor</Th>
            <Th>ad</Th>
            {format && <Th>format</Th>}
            <Th>first seen</Th>
            <Th>running</Th>
            <Th>link</Th>
          </Head>
          <tbody>
            {data.rows.map((row) => (
              <Row key={row.id}>
                <TextCell value={row.competitor} />
                <TextCell value={row.text} wide />
                {format && <TextCell value={row.format} />}
                <DateCell value={row.first_seen} />
                <StatusCell row={row} />
                <LinkCell href={row.url}>open ↗</LinkCell>
              </Row>
            ))}
          </tbody>
        </Table>
      )}
    </Synced>
  )
}
