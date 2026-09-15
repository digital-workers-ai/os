import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Tone = 'ok' | 'down' | 'unknown' | 'neutral'

const TONES: Record<Tone, string> = {
  ok: 'bg-ok/10 text-ok',
  down: 'bg-down/10 text-down',
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
  'data-testid'?: string
}) {
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
