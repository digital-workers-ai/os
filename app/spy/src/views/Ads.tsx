import { Navigate, useParams } from 'react-router-dom'
import { SubNav } from '@/components/SubNav'
import { known, PLATFORMS } from '@/lib/engines'
import { PageSection, Pending, spanOf, type RangedProps } from '@/views/ranged'

export function Ads(props: RangedProps) {
  const { platform } = useParams()
  const span = spanOf(props)
  if (!known(PLATFORMS, platform)) return <Navigate to="/ads" replace />
  if (!span) return <Pending error={props.todayError} />
  return (
    <>
      <SubNav base="ads" options={PLATFORMS} />
      <PageSection page="ads" label="Ads" />
    </>
  )
}
