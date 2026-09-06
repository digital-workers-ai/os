import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { TabbedRoute } from '@/routes'

export function useTab({ tabs, title }: TabbedRoute): [string, (value: string) => void] {
  const { tab } = useParams()
  const navigate = useNavigate()
  const current = tabs.find((t) => t.value === tab) ?? tabs[0]
  const known = current.value === tab

  useEffect(() => {
    if (!known) navigate(`../${current.value}`, { relative: 'path', replace: true })
  }, [known, current.value, navigate])

  useEffect(() => {
    const previous = document.title
    document.title = `${current.label} · ${title}`
    return () => {
      document.title = previous
    }
  }, [current.label, title])

  return [current.value, (value) => navigate(`../${value}`, { relative: 'path' })]
}
