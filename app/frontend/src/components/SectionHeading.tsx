import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function SectionHeading({ right, className, children }: { right?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <div className={cn('mb-3 flex items-center justify-between gap-3 border-b border-dbb-warm pb-2', className)}>
      <h4 className="min-w-0 text-xs font-medium uppercase tracking-wide text-dbb-muted">{children}</h4>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  )
}

export function Section({
  title,
  right,
  className,
  testId,
  children,
}: {
  title: ReactNode
  right?: ReactNode
  className?: string
  testId?: string
  children: ReactNode
}) {
  return (
    <section className={cn('mt-6 first:mt-0', className)} data-testid={testId}>
      <SectionHeading right={right}>{title}</SectionHeading>
      {children}
    </section>
  )
}
