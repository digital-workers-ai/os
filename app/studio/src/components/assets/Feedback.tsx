import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { asApiError, sendFeedback } from '@/api'
import { Section } from '@/components/assets/Section'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'

const NOTE_FIELD =
  'w-full rounded-md border border-line bg-paper p-2 text-sm text-ink placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'

export function Feedback({ seq, feedback }: { seq: number; feedback: string | null }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(feedback ?? '')
  const client = useQueryClient()
  const save = useMutation({
    mutationFn: () => sendFeedback(seq, text),
    onSuccess: () => {
      setEditing(false)
      client.invalidateQueries({ queryKey: ['asset', seq] })
    },
  })

  const edit = () => {
    setText(feedback ?? '')
    save.reset()
    setEditing(true)
  }

  const cancel = () => {
    setText(feedback ?? '')
    save.reset()
    setEditing(false)
  }

  return (
    <Section title="Feedback" testId="asset-feedback">
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={3}
            placeholder="what worked, what did not…"
            aria-label="feedback"
            className={NOTE_FIELD}
            data-testid="feedback-input"
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()} data-testid="feedback-save">
              {save.isPending ? 'Saving…' : 'Save'}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancel} data-testid="feedback-cancel">
              Cancel
            </Button>
          </div>
          {save.error && <ErrorBanner error={asApiError(save.error)} testId="feedback-error" />}
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <p className="min-w-0 flex-1 text-sm text-ink">{feedback === null ? <span className="text-muted">no note yet</span> : `“${feedback}”`}</p>
          <Button size="icon" variant="ghost" onClick={edit} aria-label="edit feedback" data-testid="feedback-edit">
            ✎
          </Button>
        </div>
      )}
      <p className="mt-2 text-xs text-muted">read by the taste agent</p>
    </Section>
  )
}
