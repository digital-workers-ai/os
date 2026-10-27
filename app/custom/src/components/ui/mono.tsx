import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Mono({
  title,
  className,
  children,
  ...rest
}: {
  title?: string
  className?: string
  children: ReactNode
  'data-testid'?: string
}) {
  return (
    <span title={title} className={cn('font-mono text-xs break-all', className)} {...rest}>
      {children}
    </span>
  )
}
