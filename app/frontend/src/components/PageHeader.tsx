import { useContext, useEffect } from 'react'
import { SetPageTitleContext } from '@/context/PageTitleContext'

export function PageHeader({ title }: { title: string }) {
  const setPageTitle = useContext(SetPageTitleContext)

  useEffect(() => {
    setPageTitle?.(title)
  }, [setPageTitle, title])

  return null
}
