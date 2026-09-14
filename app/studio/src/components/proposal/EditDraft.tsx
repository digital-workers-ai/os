import { useState } from 'react'
import type { DraftFile } from '@/api'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Mono } from '@/components/ui/mono'

const PANEL = 'inset-y-auto left-1/2 top-1/2 right-auto w-[92vw] max-w-xl -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line'

export function EditDraftDialog({
  open,
  file,
  initial,
  submitLabel,
  pending,
  onClose,
  onSave,
}: {
  open: boolean
  file: DraftFile | null
  initial: string
  submitLabel: string
  pending: boolean
  onClose: () => void
  onSave: (path: string, text: string) => void
}) {
  const [text, setText] = useState(initial)
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogContent className={PANEL} onOpenAutoFocus={() => setText(initial)} data-testid="edit-draft-dialog">
        <DialogTitle>Edit draft</DialogTitle>
        <Mono className="text-muted">{file?.path ?? 'no draft file'}</Mono>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="the draft text"
          className="min-h-[16rem] w-full rounded-md border border-input bg-transparent p-3 font-mono text-xs leading-relaxed text-ink focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          aria-label="draft text"
          data-testid="edit-draft-text"
        />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} data-testid="edit-draft-cancel">
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={file === null || text.trim() === '' || pending}
            onClick={() => file && onSave(file.path, text)}
            data-testid="edit-draft-save"
          >
            {submitLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
