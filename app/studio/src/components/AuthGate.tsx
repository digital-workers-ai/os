import { useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AUTH_EXPIRED, asApiError, me } from '@/api'
import { SignIn } from '@/components/SignIn'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'

export function AuthGate({ children }: { children: ReactNode }) {
  const who = useQuery({ queryKey: ['me'], queryFn: me, retry: false })
  const [expired, setExpired] = useState(false)
  useEffect(() => {
    const expire = () => setExpired(true)
    window.addEventListener(AUTH_EXPIRED, expire)
    return () => window.removeEventListener(AUTH_EXPIRED, expire)
  }, [])
  if (expired) return <SignIn />
  if (who.error) {
    const error = asApiError(who.error)
    if (error.status === 401) return <SignIn />
    return (
      <main className="p-6">
        <ErrorBanner error={error} />
      </main>
    )
  }
  if (!who.data) return <Loading />
  return <>{children}</>
}
