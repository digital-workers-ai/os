import { useContext, useEffect, type ReactNode } from 'react'
import { SetPageBadgeContext, SetPageTitleContext } from '@/context/PageTitleContext'

export function PageHeader({ title }: { title: string }) {
  const setPageTitle = useContext(SetPageTitleContext)

  useEffect(() => {
    setPageTitle?.(title)
  }, [setPageTitle, title])

  return null
}

export function usePageBadge(badge: ReactNode) {
  const setPageBadge = useContext(SetPageBadgeContext)

  useEffect(() => {
    setPageBadge?.(badge)
    return () => setPageBadge?.(null)
  }, [setPageBadge, badge])
}
