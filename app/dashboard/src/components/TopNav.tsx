import type { CSSProperties, ReactNode } from 'react'
import { Link, NavLink, useMatch } from 'react-router-dom'
import type { PageSpec } from '@/api'
import { PRODUCT } from '@/brand'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'

const navItem = (isActive: boolean, small = false) =>
  `flex items-center gap-2 font-medium whitespace-nowrap transition-all duration-150 ${
    small ? 'px-2.5 py-1 rounded-md text-xs' : 'px-3 py-1.5 rounded-lg text-[13px]'
  } ${isActive ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'}`

export function TopNav({
  pages,
  right,
  gray = false,
  style,
}: {
  pages: Record<string, PageSpec>
  right: ReactNode
  gray?: boolean
  style?: CSSProperties
}) {
  const menu = { filter: gray ? 'grayscale(1)' : 'grayscale(0)', transition: 'filter 1000ms ease' }
  const params = useMatch('/:parent?/:page')?.params
  const family = params?.parent ?? params?.page
  const subpages = family ? Object.entries(pages).filter(([, page]) => page.parent === family) : []
  return (
    <header className="sticky top-0 z-40 bg-surface border-b border-line" style={style} data-testid="top-nav">
      <div className="max-w-7xl mx-auto px-4 md:px-6 flex flex-wrap items-center gap-x-5">
        <Link to="/" className="flex items-center gap-1 h-14 shrink-0" data-testid="brand">
          <DigitalWorkersMark size="md" phase="done" />
          <span className="text-[15px] font-medium text-ink leading-none">{PRODUCT}</span>
        </Link>
        <nav
          className="order-last w-full md:order-none md:w-auto md:min-w-0 flex items-center gap-1 overflow-x-auto whitespace-nowrap pt-1 pb-2 md:py-1"
          style={menu}
        >
          {Object.entries(pages)
            .filter(([, page]) => page.parent === null)
            .map(([name, page]) => (
              <NavLink key={name} to={`/${name}`} className={({ isActive }) => navItem(isActive)} data-testid={`nav-${name}`}>
                {page.label}
              </NavLink>
            ))}
        </nav>
        {right && <div className="ml-auto flex items-center py-2">{right}</div>}
      </div>
      {family && subpages.length > 0 && (
        <nav
          className="max-w-7xl mx-auto px-4 md:px-6 flex items-center gap-1 overflow-x-auto whitespace-nowrap pb-2"
          style={menu}
          data-testid="sub-nav"
        >
          <NavLink to={`/${family}`} end className={({ isActive }) => navItem(isActive, true)} data-testid="subnav-all">
            All
          </NavLink>
          {subpages.map(([name, page]) => (
            <NavLink
              key={name}
              to={`/${family}/${name}`}
              className={({ isActive }) => navItem(isActive, true)}
              data-testid={`subnav-${name}`}
            >
              {page.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
