import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { lookup } from '@/api'
import { Input } from '@/components/ui/input'
import { useDebounced } from '@/lib/debounce'
import { day } from '@/lib/format'
import { humanize, summary } from '@/lib/values'
import { text, useForm, type ControlProps } from './context'

const TYPING_MS = 250
const SUGGESTED = 5

export function LookupField({ field, value, onChange, path, id, label, testId, disabled }: ControlProps) {
  const { app } = useForm()
  const typed = text(value)
  const q = useDebounced(typed.trim(), TYPING_MS)
  const found = useQuery({ queryKey: ['lookup', app.name, path, q], queryFn: () => lookup(app.name, path, q), enabled: q !== '' })
  const data = q === typed.trim() ? found.data : undefined
  const exact = data?.matches.find((match) => match.value === q)
  const entity = (field.entity ?? 'record').replace(/_/g, ' ')

  return (
    <div className="flex flex-col gap-2">
      <Input
        id={id}
        aria-label={label}
        value={typed}
        autoComplete="off"
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        data-testid={testId}
      />
      {data &&
        (exact ? (
          <p className="text-sm text-ok">
            <span>{exact.label}</span>
          </p>
        ) : data.matches.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {data.matches.slice(0, SUGGESTED).map((match) => (
              <button
                key={match.value}
                type="button"
                onClick={() => onChange(match.value)}
                className="rounded-full border border-input bg-paper px-3 py-1 text-sm text-ink hover:bg-accent"
              >
                {match.label}
              </button>
            ))}
          </div>
        ) : (
          <p>
            <span className="inline-flex rounded-full bg-wash px-2 py-0.5 text-[11px] font-medium text-ink">New {entity}</span>
          </p>
        ))}
      {field.history && data && data.history.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-paper p-3">
          <span className="text-xs font-medium text-muted">Earlier {humanize(app.title).toLowerCase()}</span>
          {data.history.map((earlier) => (
            <Link key={earlier.id} to={`/records/${earlier.id}`} className="text-sm text-ink underline-offset-4 hover:underline">
              {earlier.saved_at && <span className="mr-2 tabular-nums text-muted">{day(earlier.saved_at)}</span>}
              {summary(app, earlier.fields).join(' · ')}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
