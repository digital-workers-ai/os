import { useQuery } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'
import { getDefinition, getVisibility } from '@/api'
import { EmptyPage } from '@/components/EmptyPage'
import { MentionMatrix } from '@/components/MentionMatrix'
import { StateSection } from '@/components/StateSection'
import { SubNav } from '@/components/SubNav'
import { Card } from '@/components/ui/card'
import { ENGINES, known } from '@/lib/engines'
import { Pending, spanOf, type RangedProps } from '@/views/ranged'

export function Visibility(props: RangedProps) {
  const { engine } = useParams()
  const span = spanOf(props)
  const valid = known(ENGINES, engine)
  const visibility = useQuery({
    queryKey: ['visibility', engine ?? 'all', span],
    queryFn: () => getVisibility(engine, span ?? undefined),
    enabled: valid && !!span,
  })
  const definition = useQuery({ queryKey: ['definition'], queryFn: getDefinition, staleTime: Infinity })
  if (!valid) return <Navigate to="/visibility" replace />
  if (!span) return <Pending error={props.todayError} />
  const data = visibility.data
  const label = ENGINES.find((option) => option.value === engine)?.label ?? 'All engines'
  return (
    <>
      <SubNav base="visibility" options={ENGINES} />
      {data?.checks === 0 ? (
        <EmptyPage />
      ) : (
        <StateSection id="visibility" label={label} queries={[visibility, definition]}>
          <Card>{data && definition.data && <MentionMatrix data={data} definition={definition.data} />}</Card>
        </StateSection>
      )}
    </>
  )
}
