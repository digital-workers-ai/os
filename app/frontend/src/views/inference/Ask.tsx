import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill } from '@/components/ui/pill'
import { num, plural, relTime, short } from '@/lib/format'
import { cn } from '@/lib/utils'
import { LayerOff, useLoad } from './shared'

interface Thread {
  conversation_id: string
  created_at: string
  updated_at: string
}

interface Turn {
  question: string
  answer: string
  created_at: string
}

interface Transcript {
  conversation_id: string
  turns: Turn[]
}

interface Receipt {
  tool: string
  input: Record<string, unknown> | null
}

interface Answer {
  answer: string
  receipts: Receipt[]
  turns: number
  model: string
  prompt_version: string
  truncated?: boolean
  exhausted?: boolean
  conversation_id: string
}

function Receipts({ receipts }: { receipts: Receipt[] }) {
  if (receipts.length === 0) return <p className="text-sm text-dbb-muted">no tools were called</p>
  return (
    <div className="space-y-1.5">
      {receipts.map((r, i) => (
        <div key={i} className="flex flex-wrap items-center gap-1.5">
          <Pill>{r.tool}</Pill>
          {Object.entries(r.input ?? {}).map(([k, v]) => (
            <Chip key={k}>
              {k} <strong>{typeof v === 'string' ? v : JSON.stringify(v)}</strong>
            </Chip>
          ))}
        </div>
      ))}
    </div>
  )
}

function AnswerMeta({ answer }: { answer: Answer }) {
  return (
    <Section title={`Last answer · ${plural(answer.receipts.length, 'receipt')}`}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip>
            turns <strong>{num(answer.turns)}</strong>
          </Chip>
          {answer.exhausted && <Pill tone="err">exhausted</Pill>}
          {answer.truncated && <Pill tone="warn">truncated</Pill>}
          <Chip>
            model <strong>{answer.model}</strong>
          </Chip>
          <Chip>
            prompt <strong>{answer.prompt_version}</strong>
          </Chip>
        </div>
        <Receipts receipts={answer.receipts} />
      </div>
    </Section>
  )
}

function Conversation({ id, onAsked }: { id: string; onAsked: () => void }) {
  const transcript = useLoad(() => get<Transcript>(`/api/conversation/conversations/${encodeURIComponent(id)}`), [id])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [askError, setAskError] = useState<ApiError | null>(null)

  const ask = async () => {
    setAsking(true)
    setAskError(null)
    setAnswer(null)
    try {
      setAnswer(await post<Answer>('/api/conversation', { question, conversation_id: id }))
      setQuestion('')
      transcript.reload()
      onAsked()
    } catch (e) {
      setAskError(asApiError(e))
    } finally {
      setAsking(false)
    }
  }

  const turns = transcript.data?.turns ?? []

  return (
    <div className="space-y-4">
      <ErrorBanner error={transcript.error} />
      {transcript.loading && <Empty>loading…</Empty>}
      {transcript.data && turns.length === 0 && <Empty>no turns yet</Empty>}
      {turns.length > 0 && (
        <ol className="divide-y divide-dbb-warm/50">
          {turns.map((t, i) => (
            <li key={i} className="space-y-1 py-3 first:pt-0">
              <p className="font-medium text-dbb-charcoal">{t.question}</p>
              <p className="whitespace-pre-wrap text-sm text-dbb-muted">{t.answer}</p>
              <p className="text-[11px] text-dbb-muted" title={t.created_at}>
                {relTime(t.created_at)}
              </p>
            </li>
          ))}
        </ol>
      )}
      {answer && <AnswerMeta answer={answer} />}
      <LayerOff error={askError} />
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          ask()
        }}
      >
        <Input placeholder="ask about the business" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <Button type="submit" disabled={asking || !question.trim()}>
          {asking ? 'asking…' : 'Send'}
        </Button>
      </form>
    </div>
  )
}

export function Ask() {
  const threads = useLoad(() => get<{ conversations: Thread[] }>('/api/conversation/conversations?limit=50'), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<ApiError | null>(null)

  const create = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const r = await post<{ conversation_id: string }>('/api/conversation/conversations')
      setSelected(r.conversation_id)
      threads.reload()
    } catch (e) {
      setCreateError(asApiError(e))
    } finally {
      setCreating(false)
    }
  }

  const rows = threads.data?.conversations ?? []

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <SectionCard
        title="Threads"
        headerRight={
          <Button variant="outline" size="sm" disabled={creating} onClick={create}>
            {creating ? 'creating…' : 'New thread'}
          </Button>
        }
      >
        <div className="space-y-2">
          <ErrorBanner error={threads.error} />
          <LayerOff error={createError} />
          {threads.loading && <Empty>loading…</Empty>}
          {threads.data && rows.length === 0 && <Empty>no threads yet</Empty>}
          <div className="flex flex-col gap-1">
            {rows.map((t) => (
              <button
                key={t.conversation_id}
                type="button"
                aria-current={t.conversation_id === selected ? 'true' : undefined}
                onClick={() => setSelected(t.conversation_id)}
                className={cn(
                  'flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left hover:bg-dbb-sand/60',
                  t.conversation_id === selected && 'bg-dbb-sand',
                )}
              >
                <Mono className="text-dbb-charcoal">{short(t.conversation_id)}</Mono>
                <span className="text-xs text-dbb-muted" title={t.updated_at}>
                  {relTime(t.updated_at)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </SectionCard>
      <SectionCard
        title="Conversation"
        description={
          selected && (
            <>
              thread <Mono className="break-all">{selected}</Mono>
            </>
          )
        }
        className="min-w-0"
      >
        {selected ? <Conversation key={selected} id={selected} onAsked={threads.reload} /> : <Empty>pick a thread, or start a new one</Empty>}
      </SectionCard>
    </div>
  )
}
