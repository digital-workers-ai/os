import { useQuery } from '@tanstack/react-query'
import { getPages, type PagesResponse } from '@/api'
import { Synced } from '@/components/Synced'
import { Cell, DateCell, Head, LinkCell, NumCell, Row, Table, TextCell, Th } from '@/components/Table'
import { Mono } from '@/components/ui/mono'
import { num } from '@/lib/format'

const count = ({ total }: PagesResponse) => `${num(total)} pages`

const path = (url: string) => url.replace(/^[a-z]+:\/\/[^/]*/i, '') || '/'

export function Pages() {
  const query = useQuery({ queryKey: ['pages'], queryFn: getPages })
  return (
    <Synced slug="pages" query={query} count={count} empty={(data) => data.rows.length === 0}>
      {(data) => (
        <Table>
          <Head>
            <Th>competitor</Th>
            <Th>title</Th>
            <Th>url</Th>
            <Th right>words</Th>
            <Th>hash</Th>
            <Th>fetched on</Th>
          </Head>
          <tbody>
            {data.rows.map((row, i) => (
              <Row key={i}>
                <TextCell value={row.competitor} />
                <TextCell value={row.title} wide />
                <LinkCell href={row.url} clamp>
                  {path(row.url)}
                </LinkCell>
                <NumCell value={row.words} />
                <Cell className="whitespace-nowrap">{row.sha ? <Mono title={row.sha}>{row.sha.slice(0, 8)}</Mono> : '—'}</Cell>
                <DateCell value={row.fetched_on} />
              </Row>
            ))}
          </tbody>
        </Table>
      )}
    </Synced>
  )
}
