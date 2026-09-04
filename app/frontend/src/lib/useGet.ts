import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'

export function useGet<T>(path: string | null) {
  const [got, setGot] = useState<{ path: string; data: T | null; error: ApiError | null } | null>(null)
  useEffect(() => {
    if (!path) return
    let live = true
    get<T>(path)
      .then((data) => live && setGot({ path, data, error: null }))
      .catch((e) => live && setGot({ path, data: null, error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [path])
  const fresh = path && got?.path === path ? got : null
  return { data: path ? (fresh?.data ?? got?.data ?? null) : null, error: fresh?.error ?? null, loading: !!path && !fresh }
}
