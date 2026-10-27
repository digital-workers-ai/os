import type { CSSProperties } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'

export const PRODUCT = 'App Builder'

const TABS: [string, string, RegExp][] = [
  ['Apps', '/', /^\/(apps\/|$)/],
  ['Conversations', '/threads', /^\/(threads|new)/],
]

const navItem = (isActive: boolean) =>
  `flex items-center gap-2 font-medium whitespace-nowrap transition-all duration-150 px-3 py-1.5 rounded-lg text-[13px] ${
    isActive ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'
  }`

export function TopNav({ gray = false, style }: { gray?: boolean; style?: CSSProperties }) {
  const { pathname } = useLocation()
  const menu = { filter: gray ? 'grayscale(1)' : undefined, transition: 'filter 1000ms ease' }
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
          {TABS.map(([label, path, active]) => (
            <Link
              key={path}
              to={path}
              aria-current={active.test(pathname) ? 'page' : undefined}
              className={navItem(active.test(pathname))}
              data-testid={`nav-${label.toLowerCase()}`}
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
