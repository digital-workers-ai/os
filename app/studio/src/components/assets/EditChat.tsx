import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { asApiError, editAsset, resizeAsset, type Asset, type SkillRunRow } from '@/api'
import { Textarea } from '@/components/chat/Composer'
import { RunProgress, useSkillRun } from '@/components/chat/RunCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'

const RATIOS = ['1:1', '4:5', '9:16', '16:9']

export function EditChat({ asset, onVersion }: { asset: Asset; onVersion: () => void }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [run, setRun] = useState<SkillRunRow | null>(null)
  const live = useSkillRun(run)
  const current = live.data ?? run
  const status = current?.status
  const edit = useMutation({
    mutationFn: (ask: string) => editAsset(asset.seq, ask),
    onSuccess: ({ skill_run }) => {
      setText('')
      setRun(skill_run)
    },
  })
  const resize = useMutation({ mutationFn: (ratio: string) => resizeAsset(asset.seq, ratio), onSuccess: ({ skill_run }) => setRun(skill_run) })
  useEffect(() => {
    if (status && status !== 'running') {
      queryClient.invalidateQueries({ queryKey: ['asset', asset.seq] })
      onVersion()
    }
  }, [current?.seq, status])
  const busy = edit.isPending || resize.isPending || status === 'running'
  const error = edit.error ?? resize.error

  return (
    <section className="flex flex-col gap-2" data-testid="asset-edit">
      <h2 className="border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">Edit</h2>
      {error && <ErrorBanner error={asApiError(error)} />}
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (text.trim() && !busy) edit.mutate(text.trim())
        }}
      >
        <Textarea
          rows={3}
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={busy}
          placeholder="Say what to change"
          aria-label="edit"
          data-testid="edit-input"
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" size="sm" disabled={busy || !text.trim()} data-testid="edit-send">
            Send
          </Button>
          {asset.ratio &&
            RATIOS.filter((ratio) => ratio !== asset.ratio).map((ratio) => (
              <Button
                key={ratio}
                type="button"
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => resize.mutate(ratio)}
                data-testid={`resize-${ratio.replace(':', '-')}`}
              >
                {ratio}
              </Button>
            ))}
        </div>
      </form>
      {current && (
        <div className="rounded-lg border border-line bg-surface p-3" data-testid="edit-run">
          <RunProgress run={current} calls={live.data?.tool_calls ?? []} />
        </div>
      )}
      <p className="text-xs text-muted">Every edit makes a new version.</p>
    </section>
  )
}
