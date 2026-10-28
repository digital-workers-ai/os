import type { ReactNode } from 'react'

export function Empty({ testId = 'empty', children }: { testId?: string; children: ReactNode }) {
  return (
    <p className="py-6 text-center text-sm text-muted" data-testid={testId}>
      {children}
    </p>
  )
}
