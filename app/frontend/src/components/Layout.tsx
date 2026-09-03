import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { PRODUCT } from '@/brand'
import { TopNav } from '@/components/TopNav'
import { SetPageTitleContext } from '@/context/PageTitleContext'

export function Layout() {
  const [pageTitle, setPageTitle] = useState(PRODUCT)

  return (
    <div className="min-h-screen bg-dbb-surface">
      <TopNav />
      <main className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8">
        <h1 className="min-w-0 mb-6 md:mb-8 text-lg sm:text-xl font-medium text-dbb-charcoal truncate">{pageTitle}</h1>
        <SetPageTitleContext.Provider value={setPageTitle}>
          <Outlet />
        </SetPageTitleContext.Provider>
      </main>
    </div>
  )
}
