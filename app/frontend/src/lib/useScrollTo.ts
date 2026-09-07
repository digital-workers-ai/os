import { useEffect } from 'react'
import type { ROW } from '@/search/vocab'

export function useScrollTo(table: string, attr: (typeof ROW)[keyof typeof ROW], value: string | null, ready = true) {
  useEffect(() => {
    const row = ready && value !== null ? document.querySelector(`[data-testid="${table}"] [data-${attr}="${CSS.escape(value)}"]`) : null
    if (!row) return
    const watcher = new IntersectionObserver(
      ([entry]) => {
        watcher.disconnect()
        if (entry.intersectionRatio < 1) row.scrollIntoView({ block: 'center' })
      },
      { threshold: 1 },
    )
    watcher.observe(row)
    return () => watcher.disconnect()
  }, [table, attr, value, ready])
}
