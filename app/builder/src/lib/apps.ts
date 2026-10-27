import { useQuery } from '@tanstack/react-query'
import { getApps, type AppSummary } from '@/api'

export const extraCode = (app: AppSummary) => [...(app.script ? ['script.py'] : []), ...(app.screen ? ['screen.tsx'] : [])]

export function useAppTitles() {
  const apps = useQuery({ queryKey: ['apps'], queryFn: getApps })
  const titleOf = (name: string) => apps.data?.find((app) => app.name === name)?.title ?? name
  return { pending: apps.isPending, titleOf }
}
