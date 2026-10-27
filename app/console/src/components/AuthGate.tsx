import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { AUTH_EXPIRED, type Me } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { useGet } from '@/lib/useGet'
import { Login } from '@/views/Login'

const MeContext = createContext<Me>({ auth: 'open', email: null })

export const useMe = () => useContext(MeContext)

export function AuthGate({ children }: { children: ReactNode }) {
  const me = useGet<Me>('/api/auth/me')
  const [expired, setExpired] = useState(false)
  useEffect(() => {
    const expire = () => setExpired(true)
    window.addEventListener(AUTH_EXPIRED, expire)
    return () => window.removeEventListener(AUTH_EXPIRED, expire)
  }, [])
  if (expired) return <Login />
  if (me.loading) return <Loading />
  if (me.error?.status === 401) return <Login />
  if (me.error || !me.data) {
    return (
      <div className="p-6">
        <ErrorBanner error={me.error} />
      </div>
    )
  }
  return <MeContext.Provider value={me.data}>{children}</MeContext.Provider>
}
