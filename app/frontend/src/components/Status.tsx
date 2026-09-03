import type { ApiError } from '../api'

export function Status({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <div className="status" role="alert">
      <code>{error.status || 'network'}</code> {error.detail}
    </div>
  )
}
