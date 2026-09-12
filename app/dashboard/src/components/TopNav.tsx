import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import type { PageSpec } from '@/api'

const navItem = (isActive: boolean) =>
  `flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium whitespace-nowrap transition-all duration-150 ${
    isActive ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'
  }`

export function TopNav({ pages, right }: { pages: Record<string, PageSpec>; right: ReactNode }) {
  return (
    <header className="sticky top-0 z-40 bg-surface border-b border-line" data-testid="top-nav">
      <div className="max-w-7xl mx-auto px-4 md:px-6 flex flex-wrap items-center gap-x-5">
        <Link to="/" className="flex items-center h-14 shrink-0 text-[15px] font-medium text-ink leading-none" data-testid="brand">
          Dashboard
        </Link>
        <nav className="order-last w-full md:order-none md:w-auto md:min-w-0 flex items-center gap-1 overflow-x-auto whitespace-nowrap pt-1 pb-2 md:py-1">
          {Object.entries(pages).map(([name, page]) => (
            <NavLink key={name} to={`/${name}`} className={({ isActive }) => navItem(isActive)} data-testid={`nav-${name}`}>
              {page.label}
            </NavLink>
          ))}
        </nav>
        {right && <div className="ml-auto flex items-center py-2">{right}</div>}
      </div>
    </header>
  )
}
