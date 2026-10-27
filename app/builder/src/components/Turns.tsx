import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Suggestion, Turn } from '@/api'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Mono } from '@/components/ui/mono'
import { cn } from '@/lib/utils'

type Send = (text: string) => void

function Questions({ questions, pending, onSend }: { questions: string[]; pending: boolean; onSend: Send }) {
  const id = useId()
  const [answers, setAnswers] = useState(() => questions.map(() => ''))
  const pairs = questions.map((question, n) => [question, answers[n].trim()]).filter(([, answer]) => answer)
  return (
    <form
      className="mt-3 flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        onSend(pairs.map(([question, answer]) => `${question}\n${answer}`).join('\n\n'))
      }}
      data-testid="builder-questions"
    >
      {questions.map((question, n) => (
        <div key={n} className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-${n}`} className="font-medium text-ink">
            {question}
          </label>
          <Input
            id={`${id}-${n}`}
            value={answers[n]}
            disabled={pending}
            onChange={(event) => setAnswers(answers.map((answer, at) => (at === n ? event.target.value : answer)))}
          />
        </div>
      ))}
      <Button type="submit" variant="solid" size="sm" className="self-start" disabled={pairs.length === 0 || pending} data-testid="builder-answer">
        Send answers
      </Button>
    </form>
  )
}

function SuggestionCard({ suggestion, open, pending, onSend }: { suggestion: Suggestion; open: boolean; pending: boolean; onSend: Send }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-surface p-3" data-testid="suggestion">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium text-ink">{suggestion.title}</span>
        {suggestion.app && <Mono className="text-muted">{suggestion.app}</Mono>}
        <span className="text-xs text-muted">{suggestion.reason}</span>
      </div>
      {suggestion.app ? (
        <Button asChild size="sm" className="ml-auto shrink-0">
          <Link to={`/apps/${suggestion.app}`}>Open</Link>
        </Button>
      ) : (
        <Button
          size="sm"
          className="ml-auto shrink-0"
          disabled={!open || pending}
          onClick={() => onSend(`Draft the ${suggestion.title} app`)}
        >
          Draft it
        </Button>
      )}
    </div>
  )
}

export function Turns({
  turns,
  open,
  pending,
  empty,
  onSend,
}: {
  turns: Turn[]
  open: boolean
  pending: boolean
  empty: string
  onSend: Send
}) {
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    list.current?.lastElementChild?.scrollIntoView({ block: 'end' })
  }, [turns.length])
  if (turns.length === 0) return <Empty testId="turns-empty">{empty}</Empty>
  return (
    <ol ref={list} className="flex flex-col gap-3" data-testid="turns">
      {turns.map((turn, n) => (
        <li key={n} className={cn('flex', turn.role === 'person' ? 'justify-end' : 'justify-start')} data-testid="turn" data-role={turn.role}>
          <div className={cn('max-w-[85%] rounded-xl px-3 py-2 text-sm text-ink', turn.role === 'person' ? 'bg-wash' : 'border border-line bg-paper')}>
            <p className="whitespace-pre-wrap">{turn.text}</p>
            {turn.questions.length > 0 &&
              (open && n === turns.length - 1 ? (
                <Questions questions={turn.questions} pending={pending} onSend={onSend} />
              ) : (
                <ol className="mt-2 list-decimal pl-5 text-muted">
                  {turn.questions.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ol>
              ))}
            {turn.suggestions.length > 0 && (
              <div className="mt-3 flex flex-col gap-2">
                {turn.suggestions.map((suggestion) => (
                  <SuggestionCard key={suggestion.title} suggestion={suggestion} open={open} pending={pending} onSend={onSend} />
                ))}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}
