import { useQuery } from '@tanstack/react-query'
import { getAds } from '@/api'
import { AdsTable } from '@/components/AdsTable'

export function GoogleAds() {
  const query = useQuery({ queryKey: ['ads', 'google'], queryFn: () => getAds('google') })
  return <AdsTable slug="google-ads" query={query} format />
}
