import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { DigitalWorkersMark, type IntroPhase } from '@/components/DigitalWorkersMark'

type Step = IntroPhase | 'fadeout' | 'header' | 'all' | 'color'

const PRODUCT = 'Apps'
const WHITE = '#FFFFFF'
const GRAY = '#F8F8F8'
const EASE = 'opacity 500ms ease, background-color 1000ms ease, filter 1000ms ease'
const STEPS: [Step, number][] = [
  ['full', 0],
  ['fade', 900],
  ['collapse', 1300],
  ['done', 1900],
  ['fadeout', 2600],
  ['header', 3000],
  ['all', 3500],
  ['color', 4200],
]
const ORDER = STEPS.map(([step]) => step)

function useReveal(): Step {
  const [step, setStep] = useState<Step>(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'color' : 'full',
  )
  useEffect(() => {
    if (step === 'color') return
    const timers = STEPS.slice(1).map(([next, ms]) => setTimeout(() => setStep(next), ms))
    return () => timers.forEach(clearTimeout)
  }, [])
  return step
}

export function Layout() {
  const step = useReveal()
  const reached = (target: Step) => ORDER.indexOf(step) >= ORDER.indexOf(target)
  const phase: IntroPhase = step === 'full' || step === 'fade' || step === 'collapse' ? step : 'done'
  const gray = !reached('color')
  const tint = { backgroundColor: reached('color') ? undefined : reached('all') ? GRAY : WHITE, transition: EASE }

  return (
    <div className="min-h-screen bg-surface" style={tint}>
      {!reached('header') && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          data-testid="intro"
          style={{
            backgroundColor: WHITE,
            opacity: reached('fadeout') ? 0 : 1,
            pointerEvents: reached('fadeout') ? 'none' : undefined,
            transition: 'opacity 400ms ease',
          }}
        >
          <div className="flex items-center gap-1">
            <DigitalWorkersMark size="lg" phase={phase} />
            <span
              className="text-[28px] font-medium text-ink leading-none transition-opacity duration-300"
              style={{ opacity: phase === 'done' ? 1 : 0 }}
            >
              {PRODUCT}
            </span>
          </div>
        </div>
      )}
      <header
        className="sticky top-0 z-40 bg-surface border-b border-line"
        style={{ ...tint, opacity: reached('header') ? 1 : 0 }}
        data-testid="top-nav"
      >
        <div className="max-w-3xl mx-auto px-4 md:px-6 flex items-center">
          <Link to="/" className="flex items-center gap-1 h-14 shrink-0" data-testid="brand">
            <DigitalWorkersMark size="md" phase="done" />
            <span className="text-[15px] font-medium text-ink leading-none">{PRODUCT}</span>
          </Link>
        </div>
      </header>
      <main
        className="max-w-3xl mx-auto px-4 md:px-6 py-5 md:py-8"
        style={{ transition: EASE, opacity: reached('all') ? 1 : 0, filter: gray ? 'grayscale(1)' : undefined }}
        data-testid="page-main"
      >
        <Outlet />
      </main>
    </div>
  )
}
