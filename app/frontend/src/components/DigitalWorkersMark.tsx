import { useLayoutEffect, useRef, useState } from 'react'

export type IntroPhase = 'full' | 'fade' | 'collapse' | 'done' | 'menu'

const QUAD = 'cubic-bezier(0.455, 0.03, 0.515, 0.955)'

export function DigitalWorkersMark({
  className = '',
  size = 'sm',
  phase = 'full',
}: {
  className?: string
  size?: 'sm' | 'md'
  phase?: IntroPhase
}) {
  const text = size === 'md' ? 'text-[15px]' : 'text-[12px]'
  const dot = size === 'md' ? 'w-[7px] h-[7px]' : 'w-1.5 h-1.5'
  const fillers = useRef<(HTMLSpanElement | null)[]>([])
  const [widths, setWidths] = useState<number[] | null>(null)
  useLayoutEffect(() => {
    setWidths(fillers.current.map((el) => el?.offsetWidth ?? 0))
  }, [])
  const filler = (i: number, s: string) => (
    <span
      key={i}
      ref={(el) => {
        fillers.current[i] = el
      }}
      className="inline-block whitespace-pre"
      style={{
        overflow: 'clip',
        opacity: phase === 'full' ? 1 : 0,
        width: widths ? (phase === 'full' || phase === 'fade' ? widths[i] : 0) : undefined,
        transition: `opacity 300ms ease, width 500ms ${QUAD}`,
      }}
    >
      {s}
    </span>
  )
  return (
    <span className={`inline-flex items-center gap-1 shrink-0 ${className}`}>
      <span className={`font-logo ${text} font-medium text-dbb-charcoal whitespace-nowrap leading-none`} style={{ letterSpacing: '0.016em' }}>
        D{filler(0, 'igital ')}W{filler(1, 'orkers')}
      </span>
      <span className={`${dot} rounded-full bg-dbb-forest shrink-0`} aria-hidden />
    </span>
  )
}
