import { PageSection, Pending, spanOf, type RangedProps } from '@/views/ranged'

export function Overview(props: RangedProps) {
  const span = spanOf(props)
  if (!span) return <Pending error={props.todayError} />
  return <PageSection page="overview" label="Overview" />
}
