import { useContext, useEffect } from 'react'
import { SetPageTitleContext } from '@/context/PageTitleContext'

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  const setPageTitle = useContext(SetPageTitleContext)

  useEffect(() => {
    setPageTitle?.({ title, subtitle })
  }, [setPageTitle, title, subtitle])

  return null
}
