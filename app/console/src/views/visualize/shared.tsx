import { useRef, useState, type MouseEvent, type ReactNode } from 'react'

const HUES = [
  '#00897B',
  '#E0A030',
  '#C0553F',
  '#7B5EA7',
  '#5E9440',
  '#3B72C9',
  '#B04A72',
  '#D9773B',
  '#4A8FA8',
  '#8C7A3E',
  '#A65E9A',
  '#3D9970',
  '#C9A227',
  '#6C8EBF',
  '#B5651D',
  '#5A9BD5',
  '#9B4F3E',
]

export const typeColor = (type: string, sortedTypes: string[]) => {
  const idx = sortedTypes.indexOf(type)
  return HUES[(idx < 0 ? 0 : idx) % HUES.length]
}

export interface Hover {
  x: number
  y: number
  title: string
  lines: string[]
}

export function useHover() {
  const rootRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<Hover | null>(null)
  const show = (e: MouseEvent, title: string, lines: string[]) => {
    const box = rootRef.current?.getBoundingClientRect()
    setHover({ x: e.clientX - (box?.left ?? 0), y: e.clientY - (box?.top ?? 0), title, lines })
  }
  const hide = () => setHover(null)
  return { rootRef, hover, show, hide }
}

export function HoverTip({ hover, width }: { hover: Hover | null; width: number }) {
  if (!hover) return null
  return (
    <div
      className="pointer-events-none absolute z-10 rounded-md bg-ink px-2.5 py-1 text-[11px] text-white shadow-lg"
      style={{ left: Math.min(hover.x + 12, Math.max(0, width - 240)), top: Math.max(hover.y - 8, 0) }}
    >
      <div className="font-medium">{hover.title}</div>
      {hover.lines.map((l, i) => (
        <div key={i} className="text-white/70">
          {l}
        </div>
      ))}
    </div>
  )
}

export function TypeChip({ type, color, onClick, children }: { type: string; color: string; onClick?: () => void; children?: ReactNode }) {
  const Tag = onClick ? 'button' : 'span'
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-white px-2.5 py-0.5 text-xs text-ink ${onClick ? 'hover:bg-wash' : ''}`}
    >
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
      <span className="font-mono">{type}</span>
      {children && <span className="text-muted">{children}</span>}
    </Tag>
  )
}
