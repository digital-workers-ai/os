import type { ReactNode } from 'react'

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-dbb-muted">{children}</p>
}
