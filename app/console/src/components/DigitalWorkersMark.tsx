import { useLayoutEffect, useRef, useState } from 'react'

export type IntroPhase = 'full' | 'fade' | 'collapse' | 'done'
type MarkSize = 'sm' | 'md' | 'lg'

const QUAD = 'cubic-bezier(0.455, 0.03, 0.515, 0.955)'
const TEXT: Record<MarkSize, string> = { sm: 'text-[12px]', md: 'text-[15px]', lg: 'text-[28px]' }
const DOT: Record<MarkSize, string> = { sm: 'w-1.5 h-1.5', md: 'w-[7px] h-[7px]', lg: 'w-3 h-3' }

export function DigitalWorkersMark({
  className = '',
  size = 'sm',
  phase = 'full',
}: {
  className?: string
  size?: MarkSize
  phase?: IntroPhase
}) {
  const fillers = useRef<(HTMLSpanElement | null)[]>([])
  const [widths, setWidths] = useState<number[] | null>(null)
  useLayoutEffect(() => {
    const measure = () => setWidths(fillers.current.map((el) => el?.offsetWidth ?? 0))
    measure()
    document.fonts?.ready.then(measure)
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
        width: widths && phase !== 'full' ? (phase === 'fade' ? widths[i] : 0) : undefined,
        transition: `opacity 300ms ease, width 500ms ${QUAD}`,
      }}
    >
      {s}
    </span>
  )
  return (
    <span className={`inline-flex items-center gap-1 shrink-0 ${className}`}>
      <span className={`font-logo ${TEXT[size]} font-medium text-ink whitespace-nowrap leading-none`} style={{ letterSpacing: '0.016em' }}>
        D{filler(0, 'igital ')}W{filler(1, 'orkers')}
      </span>
      <span className={`${DOT[size]} rounded-full bg-brand shrink-0`} aria-hidden />
    </span>
  )
}
