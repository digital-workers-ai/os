import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Pill({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center whitespace-nowrap rounded-full bg-wash px-2 py-0.5 text-[11px] font-medium text-ink', className)}>
      {children}
    </span>
  )
}

export function Pills({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((item) => (
        <Pill key={item}>{item}</Pill>
      ))}
    </span>
  )
}
