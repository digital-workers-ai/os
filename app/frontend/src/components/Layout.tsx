import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { PRODUCT } from '@/brand'
import { TopNav } from '@/components/TopNav'
import { SetPageTitleContext, type PageHeading } from '@/context/PageTitleContext'

export const HEADING_RIGHT_ID = 'page-heading-right'

export function Layout() {
  const [heading, setHeading] = useState<PageHeading>({ title: PRODUCT })

  return (
    <div className="min-h-screen bg-dbb-surface">
      <TopNav />
      <main className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8">
        <div className="mb-6 md:mb-8 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-medium text-dbb-charcoal truncate">{heading.title}</h1>
            {heading.description && <p className="mt-1 text-sm text-dbb-muted">{heading.description}</p>}
          </div>
          <div id={HEADING_RIGHT_ID} className="shrink-0" />
        </div>
        <SetPageTitleContext.Provider value={setHeading}>
          <Outlet />
        </SetPageTitleContext.Provider>
      </main>
    </div>
  )
}
