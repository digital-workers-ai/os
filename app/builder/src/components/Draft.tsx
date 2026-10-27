import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Paperclip } from 'lucide-react'
import { asApiError, tryDraft, type Reading, type Turn } from '@/api'
import { Textarea } from '@/components/Composer'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'
import { base64, sampleName } from '@/lib/files'
import { humanize } from '@/lib/format'

const shown = (value: unknown): string =>
  value === null || value === undefined || value === ''
    ? '—'
    : Array.isArray(value)
      ? value.map(shown).join('; ')
      : typeof value === 'object'
        ? Object.entries(value).map(([key, entry]) => `${humanize(key)}: ${shown(entry)}`).join(', ')
        : String(value)

export function DraftCard({ turn }: { turn: Turn }) {
  return (
    <Card className="flex flex-col gap-3" data-testid="builder-draft">
      <CardTitle>The draft</CardTitle>
      <pre className="whitespace-pre-wrap break-words rounded-lg border border-line bg-surface p-3 font-mono text-xs text-ink">{turn.draft}</pre>
      {turn.problems.length > 0 && (
        <Banner tone="err" testId="builder-problems">
          <ul className="flex flex-col gap-1">
            {turn.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </Banner>
      )}
    </Card>
  )
}

function ReadingList({ reading }: { reading: Reading }) {
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="builder-reading">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {Object.entries({ ...reading.fields, ...reading.template }).map(([name, value]) => (
          <div key={name} className="contents">
            <dt className="text-muted">{humanize(name)}</dt>
            <dd className="min-w-0 break-words text-ink">{shown(value)}</dd>
          </div>
        ))}
      </dl>
      {reading.missing.length > 0 && <p className="text-xs text-muted">Not found: {reading.missing.map(humanize).join(', ')}</p>}
    </div>
  )
}

export function TryCard({ thread, draft }: { thread: string; draft: string }) {
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const tried = useMutation({
    mutationFn: async () => tryDraft(thread, file ? [{ name: sampleName(file), media_type: file.type, data: await base64(file) }] : [], text.trim() || null),
  })
  useEffect(() => tried.reset(), [draft])

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>Try it</CardTitle>
      <p className="text-sm text-muted">Read a sample photo, a PDF or what someone would say with the latest draft.</p>
      <input
        ref={picker}
        type="file"
        accept="image/*,application/pdf"
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          setFile(event.target.files?.[0] ?? null)
          event.target.value = ''
        }}
      />
      <div className="flex min-w-0 items-center gap-2">
        <Button size="sm" onClick={() => picker.current?.click()}>
          <Paperclip aria-hidden />
          {file ? 'Another sample' : 'A sample photo or PDF'}
        </Button>
        {file && <span className="truncate text-sm text-muted">{file.name}</span>}
      </div>
      <Textarea rows={2} value={text} onChange={(event) => setText(event.target.value)} placeholder="Or what someone would say" aria-label="Sample text" />
      <Button
        className="self-start"
        disabled={(!file && !text.trim()) || tried.isPending}
        onClick={() => tried.mutate()}
        data-testid="builder-try"
      >
        {tried.isPending ? 'Reading…' : 'Try it'}
      </Button>
      <ErrorBanner error={tried.error && asApiError(tried.error)} />
      {tried.data && <ReadingList reading={tried.data} />}
    </Card>
  )
}
