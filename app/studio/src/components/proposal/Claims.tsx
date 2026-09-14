import type { Claim } from '@/api'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { Panel } from '@/components/proposal/Panel'

export const claimMark = (claim: Claim) => (claim.verified ? '✓' : claim.source_ref === null ? '✗' : '⚠')

export const claimTone = (claim: Claim) => (claim.verified ? 'text-ok' : claim.source_ref === null ? 'text-err' : 'text-down')

export function ClaimRows({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) return <Empty testId="claims-empty">no claim to check</Empty>
  return (
    <ul className="divide-y divide-line/30" data-testid="claims-list">
      {claims.map((claim) => (
        <li key={`${claim.text}|${claim.source_ref ?? ''}`} className="flex flex-wrap items-baseline gap-x-2 py-1.5 text-sm" data-testid="claim-row" data-verified={claim.verified}>
          <span className="min-w-0 flex-1 text-ink">“{claim.text}”</span>
          <span className="text-muted">→</span>
          <Mono className="text-muted">{claim.source_ref ?? claim.source_kind}</Mono>
          <span className={claimTone(claim)}>{claimMark(claim)}</span>
        </li>
      ))}
    </ul>
  )
}

export function Claims({ claims }: { claims: Claim[] }) {
  return (
    <Panel title="Claims" testId="claims-panel">
      <ClaimRows claims={claims} />
    </Panel>
  )
}
