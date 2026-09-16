import type { ReactNode } from 'react'
import type { Asset } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { shortDate } from '@/lib/format'

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
  const claims = asset.claims.filter((claim) => claim.version === version)
  return (
    <section className="flex flex-col gap-2" data-testid="asset-lineage" data-version={version}>
      <h2 className="border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">Lineage</h2>
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
      <h3 className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">Claims</h3>
      {claims.length === 0 ? (
        <Empty testId="asset-claims-empty">no claims</Empty>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {claims.map((claim, i) => (
            <li key={i} className="flex gap-2 text-sm" data-testid="asset-claim" data-verified={claim.verified}>
              <span className={claim.verified ? 'text-ok' : 'text-down'} aria-label={claim.verified ? 'verified' : 'unverified'}>
                {claim.verified ? '✓' : '✗'}
              </span>
              <span className="min-w-0">
                <span className="text-ink">{claim.text}</span> <Mono className="text-muted">{claim.source_ref ?? claim.source_kind}</Mono>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
