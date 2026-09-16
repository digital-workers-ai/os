import { Navigate, useParams } from 'react-router-dom'
import { SubNav } from '@/components/SubNav'
import { ENGINES, known } from '@/lib/engines'
import { PageSection, Pending, spanOf, type RangedProps } from '@/views/ranged'

export function Visibility(props: RangedProps) {
  const { engine } = useParams()
  const span = spanOf(props)
  if (!known(ENGINES, engine)) return <Navigate to="/visibility" replace />
  if (!span) return <Pending error={props.todayError} />
  return (
    <>
      <SubNav base="visibility" options={ENGINES} />
      <PageSection page="visibility" label="Visibility" />
    </>
  )
}
