import { useReactFlow } from '@xyflow/react'
import { Maximize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { bounds, CHIP_LABELS, CHIPS, PRESET_LABELS, PRESETS, toggle, type Chip, type Preset, type Range } from '@/lib/canvas'
import { addDays } from '@/lib/calendar'
import { cn } from '@/lib/utils'

const option = (active: boolean) =>
  cn(
    'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
    active ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink',
  )

export function Filters({
  range,
  today,
  onRange,
  chips,
  onChips,
  search,
  onSearch,
}: {
  range: Range
  today: string
  onRange: (range: Range) => void
  chips: Chip[]
  onChips: (chips: Chip[]) => void
  search: string
  onSearch: (search: string) => void
}) {
  const { fitView } = useReactFlow()
  const pick = (preset: Preset) => {
    if (preset !== 'custom') return onRange({ preset })
    const current = bounds(range, today)
    onRange({ preset, from: current.from ?? addDays(today, -29), to: current.to ?? today })
  }
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="canvas-filters">
      <div className="flex items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="date range" data-testid="canvas-date-filter">
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={range.preset === preset}
            onClick={() => pick(preset)}
            className={option(range.preset === preset)}
            data-testid="canvas-date-option"
            data-preset={preset}
          >
            {PRESET_LABELS[preset]}
          </button>
        ))}
      </div>
      {range.preset === 'custom' && (
        <div className="flex items-center gap-1.5">
          <Input
            type="date"
            value={range.from}
            max={range.to}
            onChange={(e) => onRange({ ...range, from: e.target.value })}
            className="h-8 w-auto text-xs"
            aria-label="from"
            data-testid="canvas-date-from"
          />
          <span className="text-xs text-muted">–</span>
          <Input
            type="date"
            value={range.to}
            min={range.from}
            onChange={(e) => onRange({ ...range, to: e.target.value })}
            className="h-8 w-auto text-xs"
            aria-label="to"
            data-testid="canvas-date-to"
          />
        </div>
      )}
      <div className="flex items-center gap-1" role="group" aria-label="type" data-testid="canvas-chips">
        {CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            aria-pressed={chips.includes(chip)}
            onClick={() => onChips(toggle(chips, chip))}
            className={cn(
              'rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
              chips.includes(chip) ? 'border-ink bg-ink text-paper' : 'border-line bg-paper text-muted hover:text-ink',
            )}
            data-testid={`canvas-chip-${chip}`}
          >
            {CHIP_LABELS[chip]}
          </button>
        ))}
      </div>
      <Input
        type="search"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="search"
        className="h-8 w-40 text-xs"
        aria-label="search"
        data-testid="canvas-search"
      />
      <Button variant="ghost" size="sm" className="ml-auto h-8" onClick={() => void fitView()} data-testid="canvas-fit">
        <Maximize2 size={14} /> Fit
      </Button>
    </div>
  )
}
