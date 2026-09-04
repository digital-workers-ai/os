import { useEffect, useState, type ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import { PRODUCT } from '@/brand'
import { TopNav } from '@/components/TopNav'
import { SetPageBadgeContext, SetPageTitleContext } from '@/context/PageTitleContext'

type Reveal = 'none' | 'header' | 'all' | 'color'

const WHITE = '#FFFFFF'
const GRAY = '#F8F8F8'
const EASE = 'opacity 500ms ease, background-color 1000ms ease, filter 1000ms ease'
const STEPS: [Reveal, number][] = [
  ['all', 3250],
  ['color', 3950],
]

function useReveal(): Reveal {
  const [reveal, setReveal] = useState<Reveal>(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'color' : 'none',
  )
  useEffect(() => {
    if (reveal === 'color') return
    const frame = requestAnimationFrame(() => setReveal('header'))
    const timers = STEPS.map(([next, ms]) => setTimeout(() => setReveal(next), ms))
    return () => {
      cancelAnimationFrame(frame)
      timers.forEach(clearTimeout)
    }
  }, [])
  return reveal
}

export function Layout() {
  const [pageTitle, setPageTitle] = useState(PRODUCT)
  const [badge, setBadge] = useState<ReactNode>(null)
  const reveal = useReveal()
  const gray = reveal !== 'color'
  const tint = { backgroundColor: reveal === 'color' ? undefined : reveal === 'all' ? GRAY : WHITE, transition: EASE }

  return (
    <div className="min-h-screen bg-dbb-surface" style={tint}>
      <TopNav gray={gray} style={{ ...tint, opacity: reveal === 'none' ? 0 : 1 }} />
      <main
        className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8"
        style={{ transition: EASE, opacity: reveal === 'none' || reveal === 'header' ? 0 : 1, filter: gray ? 'grayscale(1)' : 'grayscale(0)' }}
      >
        <div className="mb-6 md:mb-8 flex items-center gap-3">
          <h1 className="min-w-0 text-lg sm:text-xl font-medium text-dbb-charcoal truncate">{pageTitle}</h1>
          {badge}
        </div>
        <SetPageTitleContext.Provider value={setPageTitle}>
          <SetPageBadgeContext.Provider value={setBadge}>
            <Outlet />
          </SetPageBadgeContext.Provider>
        </SetPageTitleContext.Provider>
      </main>
    </div>
  )
}
