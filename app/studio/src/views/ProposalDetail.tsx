import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import {
  approveProposal,
  asApiError,
  editDraft,
  getLook,
  getProposal,
  getSkillRun,
  redoProposal,
  rejectProposal,
  type Proposal,
} from '@/api'
import { Actions } from '@/components/proposal/Actions'
import { BuildProgress } from '@/components/proposal/BuildProgress'
import { Claims } from '@/components/proposal/Claims'
import { draftText, mainDraft, shapeOf, shortSha } from '@/components/proposal/draft'
import { EditDraftDialog } from '@/components/proposal/EditDraft'
import { Line, Panel } from '@/components/proposal/Panel'
import { Preview } from '@/components/proposal/Preview'
import { ReasonDialog } from '@/components/proposal/ReasonDialog'
import { Storyboard } from '@/components/proposal/Storyboard'
import { Variants, variantFiles } from '@/components/proposal/Variants'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill, type Tone } from '@/components/ui/pill'
import { dayLabel, hhmm, kindGlyph } from '@/lib/calendar'

const STATUS_TONES: Record<Proposal['status'], Tone> = { open: 'neutral', approved: 'ok', rejected: 'down', built: 'ok' }

function Why({ proposal }: { proposal: Proposal }) {
  return (
    <Panel title="Why" testId="why-panel">
      <Line name="theme">{proposal.theme ?? 'none recorded'}</Line>
      {proposal.evidence.map((item) => (
        <Line key={`${item.kind}|${item.ref}`} name={item.kind}>
          <Mono className="text-ink">{item.ref}</Mono>
          {item.detail && <span className="text-muted"> — {item.detail}</span>}
        </Line>
      ))}
      <Line name="skill">
        <Mono>{proposal.skill}</Mono> @ <Mono>{shortSha(proposal.skill_sha)}</Mono>
      </Line>
      <Line name="draft run">{hhmm(proposal.created_at)}</Line>
    </Panel>
  )
}

function Read({ proposal }: { proposal: Proposal }) {
  return (
    <Panel title="Read" testId="read-panel">
      {proposal.read.length === 0 ? (
        <Empty testId="read-empty">nothing recorded</Empty>
      ) : (
        proposal.read.map((entry) => (
          <p key={entry} className="py-0.5 text-sm text-ink" data-testid="read-row">
            <Mono>{entry}</Mono>
          </p>
        ))
      )}
    </Panel>
  )
}

export function ProposalDetail() {
  const params = useParams()
  const seq = Number(params.seq)
  const client = useQueryClient()
  const detail = useQuery({ queryKey: ['proposal', seq], queryFn: () => getProposal(seq), enabled: Number.isFinite(seq) })
  const proposal = detail.data

  const look = useQuery({ queryKey: ['look', proposal?.look], queryFn: () => getLook(proposal?.look as string), enabled: !!proposal?.look })

  const [started, setStarted] = useState<number | null>(null)
  const runSeq = started ?? proposal?.skill_run_seq ?? null
  const run = useQuery({
    queryKey: ['skill-run', runSeq],
    queryFn: () => getSkillRun(runSeq as number),
    enabled: runSeq !== null,
    refetchInterval: (item) => (item.state.data?.status === 'running' ? 2000 : false),
  })

  const [edits, setEdits] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState<'save' | 'approve' | null>(null)
  const [asking, setAsking] = useState<'reject' | 'redo' | null>(null)
  const [picked, setPicked] = useState<string[] | null>(null)

  const refresh = () => {
    client.invalidateQueries({ queryKey: ['proposal', seq] })
    client.invalidateQueries({ queryKey: ['proposals'] })
    client.invalidateQueries({ queryKey: ['today'] })
    client.invalidateQueries({ queryKey: ['calendar'] })
  }

  const approve = useMutation({
    mutationFn: () => approveProposal(seq),
    onSuccess: (data) => {
      setStarted(data.skill_run)
      refresh()
    },
  })
  const reject = useMutation({
    mutationFn: (reason: string) => rejectProposal(seq, reason),
    onSuccess: (data) => {
      client.setQueryData(['proposal', seq], data)
      setAsking(null)
      refresh()
    },
  })
  const redo = useMutation({
    mutationFn: (note: string) => redoProposal(seq, note),
    onSuccess: (data) => {
      setStarted(data.skill_run)
      setAsking(null)
      refresh()
    },
  })
  const edit = useMutation({
    mutationFn: (input: { path: string; text: string; approve: boolean }) => editDraft(seq, input.path, input.text),
    onSuccess: (data, input) => {
      setEdits((current) => ({ ...current, [input.path]: input.text }))
      client.setQueryData(['proposal', seq], data)
      setEditing(null)
      if (input.approve) approve.mutate()
    },
  })

  const finished = run.data?.status
  useEffect(() => {
    if (finished === 'ok' || finished === 'failed') client.invalidateQueries({ queryKey: ['proposal', seq] })
  }, [finished, client, seq])

  if (!Number.isFinite(seq)) return <Empty testId="proposal-missing">no such proposal</Empty>

  const failed = approve.error ?? reject.error ?? redo.error ?? edit.error ?? null
  const shape = proposal ? shapeOf(proposal.kind, look.data) : 'text'
  const files = proposal ? variantFiles(proposal) : []
  const selection = picked ?? files.map((file) => file.path)
  const draft = proposal ? mainDraft(proposal.drafts) : null
  const body = draft === null ? null : (edits[draft.path] ?? draftText(draft))
  const building = run.data?.status === 'running'
  const pending = approve.isPending || reject.isPending || redo.isPending || edit.isPending

  return (
    <div className="space-y-4" data-testid="proposal-detail-view" data-seq={seq} data-shape={shape} data-state={detail.isPending ? 'loading' : detail.error ? 'error' : 'ready'}>
      <Link to="/proposals" className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'h-7 -ml-2 px-2 text-muted' })} data-testid="proposal-back">
        <ArrowLeft size={14} /> Proposals
      </Link>

      {detail.error && <ErrorBanner error={asApiError(detail.error)} testId="proposal-error" />}
      {failed && <ErrorBanner error={asApiError(failed)} testId="proposal-action-error" />}
      {!proposal && !detail.error && <Loading />}

      {proposal && (
        <>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line pb-3" data-testid="proposal-title">
            <Mono className="text-muted">#{proposal.seq}</Mono>
            <span className="text-muted">
              {kindGlyph(proposal.kind)} {proposal.kind}
            </span>
            <h1 className="min-w-0 flex-1 truncate text-base font-medium text-ink">{proposal.title}</h1>
            <span className="whitespace-nowrap text-sm text-muted">
              {proposal.slot_date === null ? 'reactive' : `slot ${dayLabel(proposal.slot_date)}`}
            </span>
            {proposal.look && <span className="whitespace-nowrap text-sm text-muted">look {proposal.look}</span>}
            <Pill tone={STATUS_TONES[proposal.status]} data-testid="proposal-status">
              {proposal.status}
            </Pill>
          </div>

          {run.data?.status === 'failed' && (
            <Banner tone="err" testId="build-failed">
              build #{run.data.seq} failed — {run.data.error ?? 'no error recorded'}
            </Banner>
          )}
          {run.data?.status === 'ok' && (
            <Banner testId="build-done">
              build #{run.data.seq} finished
              {proposal.asset_seq !== null && (
                <>
                  {' · '}
                  <Link to={`/assets/${proposal.asset_seq}`} className="underline" data-testid="build-asset-link">
                    asset #{proposal.asset_seq}
                  </Link>
                </>
              )}
            </Banner>
          )}
          {proposal.reason && (
            <Banner testId="proposal-reason">
              rejected — {proposal.reason}
            </Banner>
          )}

          {building && run.data ? (
            <BuildProgress proposal={proposal} run={run.data} />
          ) : (
            <>
              <Card className="space-y-6">
                {shape === 'video' ? (
                  <Storyboard proposal={proposal} look={look.data} />
                ) : shape === 'image' ? (
                  <Variants
                    proposal={proposal}
                    files={files}
                    picked={selection}
                    onPick={(path) => setPicked(selection.includes(path) ? selection.filter((one) => one !== path) : [...selection, path])}
                  />
                ) : (
                  <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
                    <div className="space-y-6">
                      <Preview proposal={proposal} text={body} onEdit={() => setEditing('save')} />
                      <Claims claims={proposal.claims} />
                    </div>
                    <div className="space-y-6">
                      <Why proposal={proposal} />
                      <Read proposal={proposal} />
                      <Panel title="Ancestor" testId="ancestor-panel">
                        <p className="text-sm text-ink">{proposal.ancestor_ref ?? 'none (original)'}</p>
                      </Panel>
                      <Panel title="Build" testId="build-panel">
                        <Line name="renders">{proposal.build_cost ?? 'not estimated'}</Line>
                        <Line name="look">{proposal.look ?? '—'}</Line>
                      </Panel>
                    </div>
                  </div>
                )}

                <Actions
                  approveLabel={shape === 'image' ? `Approve ${selection.length} selected → build` : 'Approve → build'}
                  approveDisabled={(shape === 'image' && selection.length === 0) || proposal.status !== 'open'}
                  pending={pending}
                  onApprove={() => approve.mutate()}
                  onEditApprove={() => setEditing('approve')}
                  onReject={() => setAsking('reject')}
                  onRedo={() => setAsking('redo')}
                />
              </Card>
              {look.error && <ErrorBanner error={asApiError(look.error)} testId="look-error" />}
            </>
          )}

          <EditDraftDialog
            open={editing !== null}
            file={draft}
            initial={body ?? ''}
            submitLabel={editing === 'approve' ? 'Save and approve' : 'Save draft'}
            pending={edit.isPending}
            onClose={() => setEditing(null)}
            onSave={(path, text) => edit.mutate({ path, text, approve: editing === 'approve' })}
          />
          <ReasonDialog
            open={asking === 'reject'}
            title="Reject"
            hint="the reason is what the taste agent reads tonight"
            placeholder="why this is wrong"
            submitLabel="Reject"
            pending={reject.isPending}
            testId="reject-dialog"
            onClose={() => setAsking(null)}
            onSubmit={(value) => reject.mutate(value)}
          />
          <ReasonDialog
            open={asking === 'redo'}
            title="Redo with note"
            hint="the marketer drafts it again with this note"
            placeholder="what to change"
            submitLabel="Redo"
            pending={redo.isPending}
            testId="redo-dialog"
            onClose={() => setAsking(null)}
            onSubmit={(value) => redo.mutate(value)}
          />
        </>
      )}
    </div>
  )
}
