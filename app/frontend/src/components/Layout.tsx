import { useCallback, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { PRODUCT } from '@/brand'
import { TopNav } from '@/components/TopNav'
import { SetPageTitleContext, type PageTitleValue } from '@/context/PageTitleContext'

export function Layout() {
  const [pageTitle, setPageTitle] = useState<PageTitleValue>({ title: PRODUCT })
  const setPageTitleStable = useCallback((v: PageTitleValue) => {
    setPageTitle((prev) => (prev.title === v.title && prev.subtitle === v.subtitle ? prev : v))
  }, [])

  return (
    <div className="min-h-screen bg-dbb-surface">
      <TopNav />
      <main className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8">
        <div className="min-w-0 mb-6 md:mb-8">
          <h1 className="text-lg sm:text-xl font-medium text-dbb-charcoal truncate">{pageTitle.title}</h1>
          {pageTitle.subtitle && <p className="text-sm text-dbb-muted mt-0.5">{pageTitle.subtitle}</p>}
        </div>
        <SetPageTitleContext.Provider value={setPageTitleStable}>
          <Outlet />
        </SetPageTitleContext.Provider>
      </main>
    </div>
  )
}
