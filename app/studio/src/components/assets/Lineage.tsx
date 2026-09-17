import type { ReactNode } from 'react'
import type { Asset } from '@/api'
import { Hint } from '@/components/ui/hint'
import { Mono } from '@/components/ui/mono'
import { shortDate } from '@/lib/format'

const LINEAGE_HINT = 'Where this asset came from: the skill that made it, the calendar slot it filled, and the brand files it read.'

function Row({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 text-sm">
      <dt className="w-16 shrink-0 text-muted">{name}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

export function Lineage({ asset, version }: { asset: Asset; version: number }) {
  const read = [...new Set(asset.evidence.filter((row) => row.version === version).map((row) => row.ref))]
  return (
    <section className="flex flex-col gap-2" data-testid="asset-lineage" data-version={version}>
      <h2 className="border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">
        Lineage
        <Hint text={LINEAGE_HINT} />
      </h2>
      <dl className="flex flex-col gap-1.5">
        <Row name="skill">
          <Mono>{asset.skill}</Mono>
        </Row>
        {asset.look && <Row name="look">{asset.look}</Row>}
        {asset.ratio && <Row name="ratio">{asset.ratio}</Row>}
        {asset.slot_name && asset.slot_date && (
          <Row name="slot">
            {asset.slot_name} · {shortDate(asset.slot_date)}
          </Row>
        )}
        {read.length > 0 && (
          <Row name="read">
            <span data-testid="asset-read">{read.join(', ')}</span>
          </Row>
        )}
      </dl>
    </section>
  )
}
