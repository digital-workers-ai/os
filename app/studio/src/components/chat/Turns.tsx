import { useEffect, useRef } from 'react'
import type { Turn } from '@/api'
import { RunCard } from '@/components/chat/RunCard'
import { Empty } from '@/components/ui/empty'
import { cn } from '@/lib/utils'

export function Turns({ turns }: { turns: Turn[] }) {
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    list.current?.lastElementChild?.scrollIntoView({ block: 'end' })
  }, [turns.length])
  if (turns.length === 0) return <Empty testId="turns-empty">Ask for a post, a newsletter, a blog, an image or a carousel.</Empty>
  return (
    <ol ref={list} className="flex flex-col gap-3" data-testid="turns">
      {turns.map((turn) => (
        <li key={turn.id} className={cn('flex', turn.role === 'person' ? 'justify-end' : 'justify-start')} data-testid="turn" data-role={turn.role}>
          <div className={cn('max-w-[85%] rounded-xl px-3 py-2 text-sm text-ink', turn.role === 'person' ? 'bg-wash' : 'border border-line bg-paper')}>
            <p className="whitespace-pre-wrap">{turn.text}</p>
            {turn.skill_run && <RunCard run={turn.skill_run} />}
          </div>
        </li>
      ))}
    </ol>
  )
}
