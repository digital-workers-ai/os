import { useState, type KeyboardEvent, type TextareaHTMLAttributes } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export function Composer({ onSend, pending }: { onSend: (text: string) => Promise<unknown>; pending: boolean }) {
  const [text, setText] = useState('')
  const ready = text.trim().length > 0 && !pending
  const submit = () => {
    if (!ready) return
    onSend(text.trim()).then(
      () => setText(''),
      () => undefined,
    )
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }
  return (
    <form
      className="flex items-end gap-2 border-t border-line pt-3"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
      data-testid="composer"
    >
      <Textarea
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        disabled={pending}
        placeholder="Ask for a post, a newsletter, a blog, an image or a carousel"
        aria-label="message"
        data-testid="composer-input"
      />
      <Button type="submit" disabled={!ready} data-testid="composer-send">
        {pending ? 'sending…' : 'Send'}
      </Button>
    </form>
  )
}
