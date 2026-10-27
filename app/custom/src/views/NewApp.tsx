import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ExternalLink, Paperclip } from 'lucide-react'
import { asApiError, builderSubmit, builderTry, builderTurn, type Message, type Sent, type Turn } from '@/api'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { base64, jpeg } from '@/lib/files'
import { cn } from '@/lib/utils'
import { humanize } from '@/lib/values'

const PDF = 'application/pdf'
const BOX =
  'w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm'

const sampleOf = async (file: File): Promise<Sent> =>
  file.type === PDF ? { name: 'sample.pdf', media_type: PDF, data: await base64(file) } : jpeg(file, 'sample.jpg')

const shown = (value: unknown) =>
  value === null || value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)

export function NewApp() {
  const [messages, setMessages] = useState<Message[]>([])
  const [turn, setTurn] = useState<Turn | null>(null)
  const [text, setText] = useState('')
  const [answers, setAnswers] = useState<string[]>([])
  const [given, setGiven] = useState<string[]>([])
  const [sample, setSample] = useState<{ file: Sent; label: string } | null>(null)
  const [spoken, setSpoken] = useState('')
  const [sampleError, setSampleError] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)
  const asked = turn?.questions ?? []
  const draft = turn?.draft ?? null
  const problems = turn?.problems ?? []

  const tried = useMutation({
    mutationFn: (yaml: string) => builderTry(yaml, sample ? [sample.file] : [], spoken.trim() || null),
  })
  const submitted = useMutation({
    mutationFn: (yaml: string) => builderSubmit(messages[0]?.text ?? '', given, yaml),
  })
  const send = useMutation({
    mutationFn: ({ next }: { next: Message[]; replied: string[] }) => builderTurn(next),
    onSuccess: (answer, { next, replied }) => {
      setMessages([...next, { role: 'builder', text: answer.reply }])
      setGiven((current) => [...current, ...replied])
      setTurn(answer)
      setAnswers(answer.questions.map(() => ''))
      setText('')
      tried.reset()
    },
  })

  const pairs = asked
    .map((question, index) => [question, (answers[index] ?? '').trim()] as const)
    .filter(([, answer]) => answer)
  const said = [...pairs.map(([question, answer]) => `${question}\n${answer}`), text.trim()].filter(Boolean).join('\n\n')

  const picked = async (file: File | undefined) => {
    if (!file) return
    setSampleError(null)
    try {
      setSample({ file: await sampleOf(file), label: file.name })
    } catch (e) {
      setSampleError((e as Error).message)
    }
  }

  return (
    <div className="flex flex-col gap-5" data-testid="new-app-view" data-state="ready">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl text-ink">New app</h1>
        <p className="text-sm text-muted">
          Describe what your team needs to record. The builder asks what it needs to know in one round, drafts the app, lets you
          try it on a sample, and files it for review.
        </p>
      </div>

      {messages.length > 0 && (
        <ol className="flex flex-col gap-2">
          {messages.map((message, index) => (
            <li
              key={index}
              className={cn(
                'max-w-[85%] whitespace-pre-line rounded-xl px-3 py-2 text-sm',
                message.role === 'person' ? 'self-end bg-ink text-paper' : 'self-start border border-line bg-paper text-ink',
              )}
            >
              {message.text}
            </li>
          ))}
        </ol>
      )}

      {asked.length > 0 && (
        <Card className="flex flex-col gap-4" data-testid="builder-questions">
          {asked.map((question, index) => (
            <div key={index} className="flex flex-col gap-1.5">
              <label htmlFor={`builder-question-${index}`} className="text-sm font-medium text-ink">
                {question}
              </label>
              <Input
                id={`builder-question-${index}`}
                value={answers[index] ?? ''}
                onChange={(event) => setAnswers(answers.map((answer, at) => (at === index ? event.target.value : answer)))}
              />
            </div>
          ))}
        </Card>
      )}

      <div className="flex flex-col gap-2">
        <label htmlFor="builder-input" className="text-sm font-medium text-ink">
          {messages.length === 0 ? 'The app you need' : 'Anything else'}
        </label>
        <textarea
          id="builder-input"
          rows={messages.length === 0 ? 4 : 2}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="For example: we pour concrete and want every pour logged with a photo of the slump test."
          className={BOX}
          data-testid="builder-input"
        />
        <Button
          variant="solid"
          className="self-start"
          disabled={!said || send.isPending}
          onClick={() => send.mutate({ next: [...messages, { role: 'person', text: said }], replied: pairs.map(([, answer]) => answer) })}
          data-testid="builder-send"
        >
          {send.isPending ? 'Sending…' : 'Send'}
        </Button>
        <ErrorBanner error={send.error && asApiError(send.error)} />
      </div>

      {draft && (
        <div className="flex flex-col gap-5">
          <Card className="flex flex-col gap-3" data-testid="builder-preview">
            <h2 className="text-base font-medium text-ink">The draft</h2>
            <pre className="overflow-x-auto whitespace-pre rounded-lg border border-line bg-paper p-3 font-mono text-xs text-ink">
              {draft}
            </pre>
            {problems.length > 0 && (
              <Banner tone="err" testId="builder-problems">
                <ul className="flex flex-col gap-1">
                  {problems.map((problem) => (
                    <li key={problem}>{problem}</li>
                  ))}
                </ul>
              </Banner>
            )}
          </Card>

          <Card className="flex flex-col gap-3">
            <h2 className="text-base font-medium text-ink">Try it</h2>
            <input
              ref={picker}
              type="file"
              accept={`image/*,${PDF}`}
              className="sr-only"
              tabIndex={-1}
              onChange={(event) => {
                void picked(event.target.files?.[0])
                event.target.value = ''
              }}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={() => picker.current?.click()}>
                <Paperclip aria-hidden />
                {sample ? 'Another sample' : 'A sample photo or PDF'}
              </Button>
              {sample && <span className="text-sm text-muted">{sample.label}</span>}
            </div>
            <textarea
              rows={2}
              value={spoken}
              onChange={(event) => setSpoken(event.target.value)}
              placeholder="Or what someone would say"
              aria-label="Sample transcript"
              className={BOX}
            />
            {sampleError && <Banner tone="err">{sampleError}</Banner>}
            <Button
              className="self-start"
              disabled={(!sample && !spoken.trim()) || tried.isPending}
              onClick={() => tried.mutate(draft)}
              data-testid="builder-try"
            >
              {tried.isPending ? 'Reading…' : 'Try it'}
            </Button>
            <ErrorBanner error={tried.error && asApiError(tried.error)} />
            {tried.data && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm" data-testid="builder-reading">
                {Object.entries(tried.data.fields).map(([name, value]) => (
                  <div key={name} className="contents">
                    <dt className="text-muted">{humanize(name)}</dt>
                    <dd className="text-ink">{shown(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>

          <div className="flex flex-col gap-2">
            {submitted.data ? (
              <a
                href={submitted.data.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 self-start text-sm text-ink underline underline-offset-4"
                data-testid="builder-issue-link"
              >
                Filed as issue #{submitted.data.number}
                <ExternalLink className="size-4" aria-hidden />
              </a>
            ) : (
              <Button
                variant="solid"
                className="self-start"
                disabled={problems.length > 0 || submitted.isPending}
                onClick={() => submitted.mutate(draft)}
                data-testid="builder-submit"
              >
                Send for review
              </Button>
            )}
            <ErrorBanner error={submitted.error && asApiError(submitted.error)} />
          </div>
        </div>
      )}
    </div>
  )
}
