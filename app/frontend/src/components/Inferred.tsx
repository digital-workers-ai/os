import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { short } from '@/lib/format'

export function Inferred({ reading, sha, producedBy }: { reading?: string; sha?: string | null; producedBy?: string | null }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Pill tone="warn">inferred</Pill>
      {reading && <Mono className="text-dbb-charcoal">{reading}</Mono>}
      {sha && <Mono className="text-dbb-muted">{short(sha, 12)}</Mono>}
      {producedBy && <Mono className="text-dbb-muted">{producedBy}</Mono>}
    </span>
  )
}
