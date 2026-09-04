import { useEffect, useState } from 'react'
import { asApiError, type ApiError } from '@/api'
import { Banner, ErrorBanner } from '@/components/ui/banner'

export const PAGE_FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
export const FILL = 'min-w-0 lg:flex lg:flex-col lg:max-h-full'
export const FULL = 'min-w-0 lg:flex lg:flex-col lg:h-full'
export const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'

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
  return error.status === 409 ? <Banner className="mb-3">{error.detail}</Banner> : <ErrorBanner error={error} className="mb-3" />
}
