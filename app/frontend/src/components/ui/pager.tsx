import { Button } from '@/components/ui/button'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

export const PAGE = 5

export function Pager({
  offset,
  count,
  total,
  onPage,
  size,
  allSize,
  onSize,
  pageSize = PAGE,
  className,
}: {
  offset: number
  count: number
  total: number
  onPage: (offset: number) => void
  size: number
  allSize: number
  onSize: (size: number) => void
  pageSize?: number
  className?: string
}) {
  if (total <= pageSize) return null
  return (
    <div className={cn('mt-3 flex items-center justify-between gap-1 border-t border-dbb-warm/50 pt-2 text-sm text-dbb-muted', className)}>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - pageSize))}>
          ← Prev
        </Button>
        <span className="px-1 tabular-nums">
          {total === 0 ? '0' : `${num(offset + 1)}–${num(offset + count)}`} / {num(total)}
        </span>
        <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset + count >= total} onClick={() => onPage(offset + pageSize)}>
          Next →
        </Button>
      </div>
      <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => onSize(size >= allSize ? pageSize : allSize)}>
        {size < allSize ? 'Show all' : 'Paginate'}
      </Button>
    </div>
  )
}
