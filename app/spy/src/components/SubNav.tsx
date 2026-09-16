import { NavLink } from 'react-router-dom'
import { navItem } from '@/components/TopNav'
import type { Option } from '@/lib/engines'

export function SubNav({ base, options }: { base: string; options: Option[] }) {
  return (
    <nav className="mb-6 flex items-center gap-1 overflow-x-auto whitespace-nowrap" data-testid="sub-nav">
      <NavLink to={`/${base}`} end className={({ isActive }) => navItem(isActive, true)} data-testid="subnav-all">
        All
      </NavLink>
      {options.map((option) => (
        <NavLink
          key={option.value}
          to={`/${base}/${option.value}`}
          className={({ isActive }) => navItem(isActive, true)}
          data-testid={`subnav-${option.value}`}
        >
          {option.label}
        </NavLink>
      ))}
    </nav>
  )
}
