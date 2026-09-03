import { NavLink } from 'react-router-dom'
import { X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api, asApiError } from '@/api'
import { PRODUCT, SECTION } from '@/brand'
import { ROUTES } from '@/routes'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'

const navItem = (isActive: boolean) =>
  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 ${
    isActive ? 'bg-white text-dbb-charcoal shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-[#555] hover:bg-black/[0.04]'
  }`

const pill = 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium'

function HealthPill() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false, refetchInterval: 30_000 })
  if (health.isError) {
    return (
      <span className={`${pill} bg-dbb-clay/10 text-dbb-clay`} title={asApiError(health.error).detail}>
        backend unreachable
      </span>
    )
  }
  if (health.isPending) return <span className="text-[11px] text-dbb-muted">connecting…</span>
  const ok = health.data.status === 'ok'
  return (
    <span className={`${pill} ${ok ? 'bg-dbb-up/10 text-dbb-up' : 'bg-amber-50 text-amber-800'}`}>
      health {health.data.status}
    </span>
  )
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {open && <div className="fixed inset-0 bg-black/30 z-40 md:hidden" onClick={onClose} />}

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 bg-dbb-surface border-r border-dbb-warm flex flex-col transition-transform duration-200 ease-in-out ${
          open ? 'translate-x-0' : '-translate-x-full'
        } md:sticky md:top-0 md:h-screen md:translate-x-0 md:flex-shrink-0`}
      >
        <div className="hidden md:block px-4 py-5 border-b border-dbb-warm">
          <DigitalWorkersMark size="md" />
          <p className="text-[13px] font-medium text-dbb-charcoal leading-none mt-2">{PRODUCT}</p>
          <p className="text-[11px] font-medium text-dbb-muted uppercase tracking-wide leading-none mt-1.5">{SECTION}</p>
        </div>

        <div className="md:hidden flex items-center justify-end h-12 px-2 shrink-0">
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-dbb-muted hover:bg-dbb-sand hover:text-dbb-charcoal"
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 px-3 pt-1 pb-4 md:py-4 space-y-0.5 overflow-y-auto">
          {ROUTES.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onClose} className={({ isActive }) => navItem(isActive)}>
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-5 py-4 border-t border-dbb-warm">
          <HealthPill />
        </div>
      </aside>
    </>
  )
}
