import { useEffect, useState } from 'react'
import { Empty } from '@/components/ui/empty'

export function Loading() {
  const [shown, setShown] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setShown(true), 250)
    return () => clearTimeout(timer)
  }, [])
  return shown ? <Empty testId="loading">loading…</Empty> : null
}
