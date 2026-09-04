import type { CSSProperties } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { PRODUCT } from '@/brand'
import { ROUTES } from '@/routes'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'

const navItem = (isActive: boolean) =>
  `flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium whitespace-nowrap transition-all duration-150 ${
    isActive ? 'bg-white text-dbb-charcoal shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'
  }`

export function TopNav({ gray = false, style }: { gray?: boolean; style?: CSSProperties }) {
  const menu = { filter: gray ? 'grayscale(1)' : 'grayscale(0)', transition: 'filter 1000ms ease' }
  return (
    <header className="sticky top-0 z-40 bg-dbb-surface border-b border-dbb-warm" style={style}>
      <div className="max-w-7xl mx-auto px-4 md:px-6 flex flex-wrap items-center gap-x-5">
        <Link to="/" className="flex items-center gap-1 h-14 shrink-0">
          <DigitalWorkersMark size="md" phase="done" />
          <span className="text-[15px] font-medium text-dbb-charcoal leading-none">{PRODUCT}</span>
        </Link>
        <nav
          className="order-last w-full md:order-none md:w-auto md:min-w-0 flex items-center gap-1 overflow-x-auto whitespace-nowrap pt-1 pb-2 md:py-1"
          style={menu}
        >
          {ROUTES.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => navItem(isActive)}>
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
