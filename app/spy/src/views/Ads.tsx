import { useQuery } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'
import { asApiError, getAds, type Ad, type AdCompany } from '@/api'
import { AdCard } from '@/cards/AdCard'
import { EmptyPage } from '@/components/EmptyPage'
import { SubNav } from '@/components/SubNav'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { known, PLATFORMS } from '@/lib/engines'
import { num } from '@/lib/format'
import { Pending, spanOf, type RangedProps } from '@/views/ranged'

const heading = (company: AdCompany) => `${company.name} · ${num(company.ads)} active${company.new ? ` · ${num(company.new)} new` : ''}`

function CompanyAds({ company, ads }: { company: AdCompany; ads: Ad[] }) {
  return (
    <section className="mt-8 first:mt-0" data-testid="ads-company" data-company={company.name} data-state="ready">
      <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{heading(company)}</h2>
      {ads.length === 0 ? (
        <Empty>no ads in this range</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {ads.map((ad) => (
            <AdCard key={ad.canonical_id} ad={ad} />
          ))}
        </div>
      )}
    </section>
  )
}

export function Ads(props: RangedProps) {
  const { platform } = useParams()
  const span = spanOf(props)
  const valid = known(PLATFORMS, platform)
  const query = useQuery({
    queryKey: ['ads', platform ?? 'all', span],
    queryFn: () => getAds(platform, span ?? undefined),
    enabled: valid && !!span,
  })
  if (!valid) return <Navigate to="/ads" replace />
  if (!span) return <Pending error={props.todayError} />
  const data = query.data
  return (
    <>
      <SubNav base="ads" options={PLATFORMS} />
      <section data-testid="ads" data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
        {query.error && <ErrorBanner error={asApiError(query.error)} />}
        {!data && !query.error && <Loading />}
        {data && data.ads.length === 0 && data.companies.every((company) => company.ads === 0) && <EmptyPage />}
        {data?.companies.map((company) => (
          <CompanyAds key={company.name} company={company} ads={data.ads.filter((ad) => ad.company === company.name)} />
        ))}
      </section>
    </>
  )
}
