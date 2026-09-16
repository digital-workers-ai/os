import { PageSection, Pending, spanOf, type RangedProps } from '@/views/ranged'

export function Posts(props: RangedProps) {
  const span = spanOf(props)
  if (!span) return <Pending error={props.todayError} />
  return <PageSection page="posts" label="Posts" />
}
