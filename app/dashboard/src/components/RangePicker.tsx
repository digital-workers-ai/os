import { Input } from '@/components/ui/input'
import { shortDate } from '@/lib/format'
import { bounds, PRESET_LABELS, PRESETS, type Preset, type Range } from '@/lib/range'
import { cn } from '@/lib/utils'

export function RangePicker({ range, today, onChange }: { range: Range; today: string; onChange: (range: Range) => void }) {
  const current = bounds(range, today)
  const pick = (preset: Preset) => onChange(preset === 'custom' ? { preset, ...current } : { preset })
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="range-picker">
      <div className="flex items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="date range">
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={range.preset === preset}
            onClick={() => pick(preset)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              range.preset === preset ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink',
            )}
            data-testid="range-option"
            data-preset={preset}
          >
            {PRESET_LABELS[preset]}
          </button>
        ))}
      </div>
      {range.preset === 'custom' ? (
        <div className="flex items-center gap-1.5">
          <Input
            type="date"
            value={range.from}
            max={range.to}
            onChange={(e) => onChange({ ...range, from: e.target.value })}
            className="h-8 w-auto text-xs"
            aria-label="from"
            data-testid="range-from"
          />
          <span className="text-xs text-muted">–</span>
          <Input
            type="date"
            value={range.to}
            min={range.from}
            onChange={(e) => onChange({ ...range, to: e.target.value })}
            className="h-8 w-auto text-xs"
            aria-label="to"
            data-testid="range-to"
          />
        </div>
      ) : (
        <span className="text-xs tabular-nums text-muted" data-testid="range-bounds">
          {shortDate(current.from)} – {shortDate(current.to)}
        </span>
      )}
    </div>
  )
}
