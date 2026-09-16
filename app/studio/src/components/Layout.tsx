import { Outlet } from 'react-router-dom'
import { TopNav } from '@/components/TopNav'

export function Layout() {
  return (
    <div className="min-h-screen bg-surface">
      <TopNav />
      <main className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8" data-testid="page-main">
        <Outlet />
      </main>
    </div>
  )
}
