import type { QueryClient } from '@tanstack/react-query'
import type { NavigateFunction } from 'react-router-dom'
import type { Thread } from '@/api'

export function openThread(queryClient: QueryClient, navigate: NavigateFunction, thread: Thread, replace = false) {
  queryClient.setQueryData(['thread', thread.id], thread)
  queryClient.invalidateQueries({ queryKey: ['threads'] })
  navigate(`/threads/${thread.id}`, { replace })
}
