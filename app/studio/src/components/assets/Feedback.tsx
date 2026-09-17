import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { asApiError, sendFeedback, type Asset } from '@/api'
import { Textarea } from '@/components/chat/Composer'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'

const FEEDBACK_HINT = 'A note kept with the asset and read by the nightly taste agent, which turns a correction that keeps coming back into a lesson in the skill.'

export function Feedback({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const save = useMutation({
    mutationFn: (note: string) => sendFeedback(asset.seq, note),
    onSuccess: (detail) => {
      queryClient.setQueryData(['asset', asset.seq], detail)
      setEditing(false)
    },
  })
  const open = () => {
    setText(asset.feedback ?? '')
    setEditing(true)
  }

  return (
    <section className="flex flex-col gap-2" data-testid="asset-feedback">
      <div className="flex items-center justify-between border-b border-line pb-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted">
          Feedback
          <Hint text={FEEDBACK_HINT} />
        </h2>
        {!editing && (
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={open} aria-label="edit feedback" data-testid="feedback-edit">
            ✎
          </Button>
        )}
      </div>
      {save.error && <ErrorBanner error={asApiError(save.error)} />}
      {editing ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate(text)
          }}
        >
          <Textarea
            rows={3}
            value={text}
            onChange={(event) => setText(event.target.value)}
            disabled={save.isPending}
            placeholder="What worked, what to change next time"
            aria-label="feedback"
            data-testid="feedback-input"
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={save.isPending} data-testid="feedback-save">
              Save
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={save.isPending} data-testid="feedback-cancel">
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <p className={cn('whitespace-pre-wrap text-sm', asset.feedback ? 'text-ink' : 'text-muted')} data-testid="feedback-note">
          {asset.feedback || 'no note yet'}
        </p>
      )}
      <p className="text-xs text-muted">The taste agent reads this every night.</p>
    </section>
  )
}
