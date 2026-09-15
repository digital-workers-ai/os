import { useQuery } from '@tanstack/react-query'
import { getAds } from '@/api'
import { AdsTable } from '@/components/AdsTable'

export function MetaAds() {
  const query = useQuery({ queryKey: ['ads', 'meta'], queryFn: () => getAds('meta') })
  return <AdsTable slug="meta-ads" query={query} />
}
