import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, asApiError } from '@/api'
import { PRODUCT, SECTION } from '@/brand'
import { ROUTES } from '@/routes'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'
import { Pill } from '@/components/ui/pill'

const navItem = (isActive: boolean) =>
  `flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium whitespace-nowrap transition-all duration-150 ${
    isActive ? 'bg-white text-dbb-charcoal shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'
  }`

function HealthPill() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false, refetchInterval: 30_000 })
  if (health.isError) {
    return (
      <Pill tone="err" title={asApiError(health.error).detail}>
        backend unreachable
      </Pill>
    )
  }
  if (health.isPending) return <span className="text-[11px] text-dbb-muted">connecting…</span>
  return <Pill tone={health.data.status === 'ok' ? 'ok' : 'warn'}>health {health.data.status}</Pill>
}

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 bg-dbb-surface border-b border-dbb-warm">
      <div className="max-w-7xl mx-auto px-4 md:px-6 flex flex-wrap items-center gap-x-5">
        <div className="flex items-center gap-3 h-14 shrink-0">
          <DigitalWorkersMark size="md" />
          <span className="h-5 w-px bg-dbb-warm" aria-hidden />
          <span className="text-[13px] font-medium text-dbb-charcoal leading-none">{PRODUCT}</span>
          <span className="text-[10px] font-medium uppercase tracking-wide text-dbb-muted leading-none">{SECTION}</span>
        </div>
        <nav className="order-last w-full md:order-none md:w-auto md:min-w-0 flex items-center gap-1 overflow-x-auto whitespace-nowrap pt-1 pb-2 md:py-1">
          {ROUTES.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => navItem(isActive)}>
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto shrink-0">
          <HealthPill />
        </div>
      </div>
    </header>
  )
}
