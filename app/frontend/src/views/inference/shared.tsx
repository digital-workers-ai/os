import { useEffect, useState } from 'react'
import { asApiError, type ApiError } from '../../api'
import { Status } from '../../components/Status'

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
  if (error.status !== 409) return <Status error={error} />
  return (
    <div className="layer-off" role="status">
      <code>409</code> {error.detail}
    </div>
  )
}

export function Enabled({ on }: { on: boolean }) {
  return <span className={'pill ' + (on ? 'ok' : 'warn')}>{on ? 'enabled' : 'disabled'}</span>
}

export const short = (s: string) => s.slice(0, 12)
