import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Panel({ title, testId, className, children }: { title: string; testId: string; className?: string; children: ReactNode }) {
  return (
    <section className={className} data-testid={testId}>
      <h3 className="mb-2 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{title}</h3>
      {children}
    </section>
  )
}

export function Line({ name, className, children }: { name: string; className?: string; children: ReactNode }) {
  return (
    <div className={cn('flex gap-3 py-0.5 text-sm', className)}>
      <span className="w-20 shrink-0 text-muted">{name}</span>
      <span className="min-w-0 flex-1 text-ink">{children}</span>
    </div>
  )
}
