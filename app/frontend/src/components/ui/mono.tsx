import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Mono({ title, className, children }: { title?: string; className?: string; children: ReactNode }) {
  return (
    <span title={title} className={cn('font-mono text-xs', className)}>
      {children}
    </span>
  )
}
