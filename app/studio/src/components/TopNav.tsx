import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS: [string, string][] = [
  ['/', 'Today'],
  ['/calendar', 'Calendar'],
  ['/proposals', 'Proposals'],
  ['/canvas', 'Canvas'],
  ['/competitors/swipe', 'Competitors'],
  ['/assets', 'Assets'],
  ['/context/brand', 'Context'],
  ['/activity', 'Activity'],
]

export function TopNav() {
  return (
    <nav className="flex flex-wrap items-center gap-1" data-testid="top-nav">
      {TABS.map(([to, label]) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          data-testid={`nav-${label.toLowerCase()}`}
          className={({ isActive }) =>
            cn(
              'rounded-md px-3 py-1.5 text-sm transition-colors',
              isActive ? 'bg-ink text-paper' : 'text-muted hover:bg-wash hover:text-ink',
            )
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function SubNav({ base, tabs, current }: { base: string; tabs: [string, string][]; current: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-line pb-2" data-testid="sub-nav">
      {tabs.map(([slug, label]) => (
        <NavLink
          key={slug}
          to={`${base}/${slug}`}
          data-testid={`subnav-${slug}`}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs transition-colors',
            current === slug ? 'bg-wash font-medium text-ink' : 'text-muted hover:text-ink',
          )}
        >
          {label}
        </NavLink>
      ))}
    </div>
  )
}
