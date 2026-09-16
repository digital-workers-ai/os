import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

export function Stat({ n, label, className }: { n: number; label: string; className?: string }) {
  return (
    <span className={cn('whitespace-nowrap', className)}>
      <span className="font-medium tabular-nums text-ink">{num(n)}</span> <span className="text-[11px] text-muted">{label}</span>
    </span>
  )
}
