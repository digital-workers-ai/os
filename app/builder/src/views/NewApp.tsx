import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { asApiError, createThread, type ApiError } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { openThread } from '@/lib/threads'

export function NewApp() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const started = useRef(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true
    createThread().then(
      (thread) => openThread(queryClient, navigate, thread, true),
      (e) => setError(asApiError(e)),
    )
  }, [])

  return (
    <div data-testid="new-app-view" data-state={error ? 'error' : 'loading'}>
      {error ? <ErrorBanner error={error} /> : <Loading />}
    </div>
  )
}
