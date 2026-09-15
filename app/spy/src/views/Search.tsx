import { useQuery } from '@tanstack/react-query'
import { getRankings, type RankingsResponse } from '@/api'
import { Synced } from '@/components/Synced'
import { Cell, Head, Row, Table, Th } from '@/components/Table'
import { num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const count = ({ keywords, engine, checked_on }: RankingsResponse) =>
  [`${num(keywords.length)} keywords`, engine, checked_on && `checked ${shortDate(checked_on)}`].filter(Boolean).join(' · ')

function Position({ value, ours }: { value: number | null; ours: boolean }) {
  return (
    <Cell className={cn('whitespace-nowrap text-right tabular-nums', ours ? 'font-semibold text-ink' : 'text-muted')}>
      {value === null ? '—' : `#${num(value)}`}
    </Cell>
  )
}

export function Search() {
  const query = useQuery({ queryKey: ['rankings'], queryFn: getRankings })
  return (
    <Synced slug="search" query={query} count={count} empty={(data) => data.keywords.length === 0}>
      {(data) => (
        <Table>
          <Head>
            <Th>keyword</Th>
            {data.domains.map(({ domain, name }) => (
              <Th key={domain} right strong={domain === data.us}>
                {name}
              </Th>
            ))}
          </Head>
          <tbody>
            {data.keywords.map((row) => (
              <Row key={row.keyword}>
                <Cell className="whitespace-nowrap font-medium text-ink">{row.keyword}</Cell>
                {data.domains.map(({ domain }) => (
                  <Position key={domain} value={row.positions[domain] ?? null} ours={domain === data.us} />
                ))}
              </Row>
            ))}
          </tbody>
        </Table>
      )}
    </Synced>
  )
}
