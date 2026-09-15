import { useQuery } from '@tanstack/react-query'
import { getAnswers, type AnswersResponse } from '@/api'
import { Synced } from '@/components/Synced'
import { Cell, Head, NumCell, Row, Table, TextCell, Th } from '@/components/Table'
import { num, percent, shortDate } from '@/lib/format'

const count = ({ prompts, engines, checked_on }: AnswersResponse) =>
  [`${num(prompts.length)} prompts`, `${num(engines.length)} engines`, checked_on && `checked ${shortDate(checked_on)}`]
    .filter(Boolean)
    .join(' · ')

export function Answers() {
  const query = useQuery({ queryKey: ['answers'], queryFn: getAnswers })
  return (
    <Synced slug="answers" query={query} count={count} empty={(data) => data.prompts.length === 0}>
      {(data) => (
        <>
          <Table>
            <Head>
              <Th>prompt</Th>
              {data.engines.map((engine) => (
                <Th key={engine}>{engine}</Th>
              ))}
            </Head>
            <tbody>
              {data.prompts.map((row) => (
                <Row key={row.prompt}>
                  <TextCell value={row.prompt} wide />
                  {data.engines.map((engine) => (
                    <TextCell key={engine} value={(row.named[engine] ?? []).join(', ')} />
                  ))}
                </Row>
              ))}
            </tbody>
          </Table>
          <h2 className="mt-8 mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">Brands</h2>
          <Table>
            <Head>
              <Th>brand</Th>
              <Th right>named</Th>
              <Th right>asked</Th>
              <Th right>rate</Th>
            </Head>
            <tbody>
              {data.brands.map((row) => (
                <Row key={row.brand}>
                  <TextCell value={row.brand} wide />
                  <NumCell value={row.named} />
                  <NumCell value={row.asked} />
                  <Cell className="whitespace-nowrap text-right tabular-nums text-ink">{percent(row.rate)}</Cell>
                </Row>
              ))}
            </tbody>
          </Table>
        </>
      )}
    </Synced>
  )
}
