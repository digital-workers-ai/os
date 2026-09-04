import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'

export function useGet<T>(path: string | null, version = 0) {
  const [got, setGot] = useState<{ path: string; version: number; data: T | null; error: ApiError | null } | null>(null)
  useEffect(() => {
    if (!path) return
    let live = true
    get<T>(path)
      .then((data) => live && setGot({ path, version, data, error: null }))
      .catch((e) => live && setGot({ path, version, data: null, error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [path, version])
  const fresh = path && got?.path === path && got.version === version ? got : null
  return { data: path ? (fresh?.data ?? got?.data ?? null) : null, error: fresh?.error ?? null, loading: !!path && !fresh }
}
