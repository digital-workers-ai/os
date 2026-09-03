import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Tone = 'ok' | 'warn' | 'err' | 'unknown' | 'neutral'

const TONES: Record<Tone, string> = {
  ok: 'bg-dbb-up/10 text-dbb-up',
  warn: 'bg-amber-50 text-amber-800',
  err: 'bg-dbb-clay/10 text-dbb-clay',
  unknown: 'border border-dashed border-dbb-warm text-dbb-muted',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

export function Pill({
  tone = 'neutral',
  title,
  className,
  children,
}: {
  tone?: Tone
  title?: string
  className?: string
  children: ReactNode
}) {
  return (
    <span
      title={title}
      className={cn('inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone], className)}
    >
      {children}
    </span>
  )
}

export function Chip({ title, className, children }: { title?: string; className?: string; children: ReactNode }) {
  return (
    <span
      title={title}
      className={cn(
        'inline-block rounded-full border border-dbb-warm px-2 py-0.5 text-[11px] text-dbb-muted [&_strong]:font-medium [&_strong]:text-dbb-charcoal',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function FilterChip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
        on ? 'border-dbb-warm bg-dbb-sand text-dbb-charcoal' : 'border-dbb-warm/50 text-dbb-muted hover:border-dbb-warm',
      )}
    >
      {children}
    </button>
  )
}
