import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '../../api'
import { Empty, Panel, num, relTime } from '../../components/Panel'
import { Status } from '../../components/Status'
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
  if (receipts.length === 0) return <Empty>no tools were called</Empty>
  return (
    <div className="receipts">
      {receipts.map((r, i) => (
        <div key={i} className="chips">
          <span className="chip">
            <strong>{r.tool}</strong>
          </span>
          {Object.entries(r.input ?? {}).map(([k, v]) => (
            <span key={k} className="chip">
              {k} <strong>{typeof v === 'string' ? v : JSON.stringify(v)}</strong>
            </span>
          ))}
        </div>
      ))}
    </div>
  )
}

function AnswerView({ answer }: { answer: Answer }) {
  return (
    <div className="answer">
      <div>
        <div className="chips">
          <span className="chip">
            turns <strong>{num(answer.turns)}</strong>
          </span>
          {answer.exhausted && <span className="pill err">exhausted</span>}
          {answer.truncated && <span className="pill warn">truncated</span>}
          <span className="chip">
            model <strong>{answer.model}</strong>
          </span>
          <span className="chip">
            prompt <strong>{answer.prompt_version}</strong>
          </span>
        </div>
        <pre className="prose">{answer.answer}</pre>
      </div>
      <div>
        <h3>Receipts ({answer.receipts.length})</h3>
        <Receipts receipts={answer.receipts} />
      </div>
    </div>
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
    <div className="panel-body">
      <h3>
        Transcript <code className="dim">{id}</code>
      </h3>
      <Status error={transcript.error} />
      {transcript.loading && <Empty>loading…</Empty>}
      {transcript.data && turns.length === 0 && <Empty>no turns yet</Empty>}
      {turns.length > 0 && (
        <ol className="turns">
          {turns.map((t, i) => (
            <li key={i} className="turn">
              <div className="q">{t.question}</div>
              <pre className="prose">{t.answer}</pre>
              <div className="dim" title={t.created_at}>
                {relTime(t.created_at)}
              </div>
            </li>
          ))}
        </ol>
      )}
      <h3>Question</h3>
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault()
          ask()
        }}
      >
        <input
          className="wide"
          placeholder="ask about the business"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn" type="submit" disabled={asking || !question.trim()}>
          {asking ? 'asking…' : 'Ask'}
        </button>
      </form>
      <LayerOff error={askError} />
      {answer && <AnswerView answer={answer} />}
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
    <Panel
      title={`Ask${threads.data ? ` (${rows.length} threads)` : ''}`}
      actions={
        <button className="btn" disabled={creating} onClick={create}>
          {creating ? 'creating…' : 'New thread'}
        </button>
      }
    >
      <div className="ask">
        <aside className="threads">
          <Status error={threads.error} />
          <Status error={createError} />
          {threads.loading && <Empty>loading…</Empty>}
          {threads.data && rows.length === 0 && <Empty>no threads yet</Empty>}
          {rows.map((t) => (
            <button
              key={t.conversation_id}
              className="thread"
              aria-current={t.conversation_id === selected ? 'true' : undefined}
              onClick={() => setSelected(t.conversation_id)}
            >
              <code>{t.conversation_id.slice(0, 8)}</code>
              <span className="dim" title={t.updated_at}>
                {relTime(t.updated_at)}
              </span>
            </button>
          ))}
        </aside>
        {selected ? (
          <Conversation key={selected} id={selected} onAsked={threads.reload} />
        ) : (
          <Empty>pick a thread, or start a new one</Empty>
        )}
      </div>
    </Panel>
  )
}
