import { Outlet } from 'react-router-dom'
import { TopNav } from '@/components/TopNav'

export function Layout() {
  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-4 px-4 py-3 sm:px-6">
          <span className="font-logo text-lg tracking-tight" data-testid="studio-mark">
            Studio
          </span>
          <TopNav />
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6" data-testid="studio-main">
        <Outlet />
      </main>
    </div>
  )
}
