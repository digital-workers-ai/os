import type { ReactNode } from 'react'

export function Section({ title, testId, children }: { title: string; testId: string; children: ReactNode }) {
  return (
    <section data-testid={testId}>
      <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  )
}

export function Line({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 py-0.5 text-sm">
      <span className="w-20 shrink-0 text-muted">{name}</span>
      <span className="min-w-0 flex-1 text-ink">{children}</span>
    </div>
  )
}
