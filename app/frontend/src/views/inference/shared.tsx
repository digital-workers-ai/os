import { useEffect, useState } from 'react'
import { asApiError, type ApiError } from '@/api'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Pill } from '@/components/ui/pill'

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setData(null)
    setError(null)
    load()
      .then((d) => {
        if (live) setData(d)
      })
      .catch((e) => {
        if (live) setError(asApiError(e))
      })
    return () => {
      live = false
    }
  }, [...deps, tick])
  return { data, error, loading: data === null && error === null, reload: () => setTick((t) => t + 1) }
}

export function LayerOff({ error }: { error: ApiError | null }) {
  if (!error) return null
  return error.status === 409 ? <Banner>{error.detail}</Banner> : <ErrorBanner error={error} />
}

export function Enabled({ on }: { on: boolean }) {
  return <Pill tone={on ? 'ok' : 'warn'}>{on ? 'enabled' : 'disabled'}</Pill>
}

export const ALL = '*'
