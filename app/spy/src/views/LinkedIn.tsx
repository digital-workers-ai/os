import { useQuery } from '@tanstack/react-query'
import { getPosts, type PostsResponse } from '@/api'
import { Synced } from '@/components/Synced'
import { DateCell, Head, LinkCell, NumCell, Row, Table, TextCell, Th } from '@/components/Table'
import { num } from '@/lib/format'

const count = ({ total }: PostsResponse) => `${num(total)} posts`

export function LinkedIn() {
  const query = useQuery({ queryKey: ['posts'], queryFn: getPosts })
  return (
    <Synced slug="linkedin" query={query} count={count} empty={(data) => data.rows.length === 0}>
      {(data) => (
        <Table>
          <Head>
            <Th>competitor</Th>
            <Th>post</Th>
            <Th>posted</Th>
            <Th right>reactions</Th>
            <Th right>comments</Th>
            <Th>link</Th>
          </Head>
          <tbody>
            {data.rows.map((row, i) => (
              <Row key={i}>
                <TextCell value={row.competitor} />
                <TextCell value={row.text} wide />
                <DateCell value={row.posted_at} />
                <NumCell value={row.likes} />
                <NumCell value={row.comments} />
                <LinkCell href={row.url}>open ↗</LinkCell>
              </Row>
            ))}
          </tbody>
        </Table>
      )}
    </Synced>
  )
}
