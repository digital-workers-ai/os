import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Tone = 'ok' | 'warn' | 'err' | 'unknown' | 'neutral'

type Marked = { 'data-testid'?: string }

const TONES: Record<Tone, string> = {
  ok: 'bg-ok/10 text-ok',
  warn: 'bg-amber-50 text-amber-800',
  err: 'bg-err/10 text-err',
  unknown: 'border border-dashed border-line text-muted',
  neutral: 'bg-wash text-ink',
}

export function Pill({
  tone = 'neutral',
  title,
  className,
  children,
  ...rest
}: {
  tone?: Tone
  title?: string
  className?: string
  children: ReactNode
} & Marked) {
  return (
    <span
      title={title}
      className={cn('inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone], className)}
      {...rest}
    >
      {children}
    </span>
  )
}

export function Chip({ title, className, children, ...rest }: { title?: string; className?: string; children: ReactNode } & Marked) {
  return (
    <span
      title={title}
      className={cn(
        'inline-block break-all rounded-full border border-line px-2 py-0.5 text-[11px] text-muted [&_strong]:font-medium [&_strong]:text-ink',
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  )
}

export function FilterChip({ on, onClick, children, ...rest }: { on: boolean; onClick: () => void; children: ReactNode } & Marked) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
        on ? 'border-line bg-wash text-ink' : 'border-line/50 text-muted hover:border-line',
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
