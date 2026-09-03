import { useCallback, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { PRODUCT } from '@/brand'
import { Sidebar } from '@/components/Sidebar'
import { SetPageTitleContext, type PageTitleValue } from '@/context/PageTitleContext'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [pageTitle, setPageTitle] = useState<PageTitleValue>({ title: PRODUCT })
  const setPageTitleStable = useCallback((v: PageTitleValue) => {
    setPageTitle((prev) => (prev.title === v.title && prev.subtitle === v.subtitle ? prev : v))
  }, [])

  return (
    <div className="flex min-h-screen bg-dbb-surface">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="flex-1 overflow-auto min-w-0">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8">
          <div className="flex items-center gap-3 min-w-0 mb-6 md:mb-8">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-lg text-dbb-charcoal hover:bg-dbb-sand"
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="min-w-0">
              <h1 className="text-lg sm:text-xl font-medium text-dbb-charcoal truncate">{pageTitle.title}</h1>
              {pageTitle.subtitle && <p className="text-sm text-dbb-muted mt-0.5">{pageTitle.subtitle}</p>}
            </div>
            <span className="md:hidden ml-auto pl-2 text-[12px] font-medium text-dbb-charcoal whitespace-nowrap leading-none">
              {PRODUCT}
            </span>
          </div>
          <SetPageTitleContext.Provider value={setPageTitleStable}>
            <Outlet />
          </SetPageTitleContext.Provider>
        </div>
      </main>
    </div>
  )
}
