import { Link } from 'react-router-dom'
import type { Asset } from '@/api'
import { Line, Section } from '@/components/assets/Section'
import { Mono } from '@/components/ui/mono'

export function Lineage({ asset }: { asset: Asset }) {
  const verified = asset.claims.filter((claim) => claim.verified).length
  const total = asset.claims.length
  return (
    <Section title="Lineage" testId="asset-lineage">
      <Line name="source">
        {asset.proposal_seq === null ? (
          'from chat'
        ) : (
          <Link to={`/proposals/${asset.proposal_seq}`} className="underline-offset-4 hover:underline">
            proposal #{asset.proposal_seq}
          </Link>
        )}
      </Line>
      <Line name="skill">
        <Mono title={asset.skill_sha}>
          {asset.skill} @ {asset.skill_sha.slice(0, 7)}
        </Mono>
      </Line>
      <Line name="look">{asset.look ?? '—'}</Line>
      <Line name="ancestor">{asset.ancestor_ref ?? '—'}</Line>
      <Line name="read">{asset.read.length === 0 ? '—' : asset.read.join(', ')}</Line>
      <Line name="claims">
        {total === 0 ? (
          '—'
        ) : (
          <>
            {verified}/{total} <span className={verified === total ? 'text-ok' : 'text-down'}>{verified === total ? '✓' : '⚠'}</span>
          </>
        )}
      </Line>
      {total > 0 && (
        <ul className="mt-2 space-y-1 text-xs">
          {asset.claims.map((claim, index) => (
            <li key={index} className="flex gap-2">
              <span className={claim.verified ? 'text-ok' : 'text-down'}>{claim.verified ? '✓' : '✗'}</span>
              <span className="min-w-0 flex-1">
                <span className="text-ink">{claim.text}</span>{' '}
                <Mono className="text-muted">
                  {claim.source_kind}
                  {claim.source_ref === null ? '' : ` ${claim.source_ref}`}
                </Mono>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}
