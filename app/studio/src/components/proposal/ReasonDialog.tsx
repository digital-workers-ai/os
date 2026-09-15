import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

const PANEL = 'inset-y-auto left-1/2 top-1/2 right-auto w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line'

export function ReasonDialog({
  open,
  title,
  hint,
  placeholder,
  submitLabel,
  pending,
  testId,
  onClose,
  onSubmit,
}: {
  open: boolean
  title: string
  hint: string
  placeholder: string
  submitLabel: string
  pending: boolean
  testId: string
  onClose: () => void
  onSubmit: (value: string) => void
}) {
  const [value, setValue] = useState('')
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogContent className={PANEL} onOpenAutoFocus={() => setValue('')} data-testid={testId}>
        <DialogTitle>{title}</DialogTitle>
        <p className="text-sm text-muted">{hint}</p>
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          aria-label={title}
          data-testid={`${testId}-input`}
        />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} data-testid={`${testId}-cancel`}>
            Cancel
          </Button>
          <Button size="sm" disabled={value.trim() === '' || pending} onClick={() => onSubmit(value.trim())} data-testid={`${testId}-submit`}>
            {submitLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
