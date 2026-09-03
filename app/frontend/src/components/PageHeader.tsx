import { useContext, useEffect } from 'react'
import { SetPageTitleContext } from '@/context/PageTitleContext'

export function PageHeader({ title, description }: { title: string; description?: string }) {
  const setPageTitle = useContext(SetPageTitleContext)

  useEffect(() => {
    setPageTitle?.({ title, description })
  }, [setPageTitle, title, description])

  return null
}
