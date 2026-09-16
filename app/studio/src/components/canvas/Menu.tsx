import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Copy, Download, Maximize2, Pencil } from 'lucide-react'
import type { CanvasNode } from '@/api'

export interface MenuState {
  x: number
  y: number
  node: CanvasNode
}

const item = 'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm text-ink hover:bg-wash'

export function Menu({ menu, onOpen, onClose }: { menu: MenuState | null; onOpen: (node: CanvasNode) => void; onClose: () => void }) {
  const navigate = useNavigate()
  const ref = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setCopied(false)
    if (!menu) return
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as globalThis.Node)) onClose()
    }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [menu, onClose])

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

  if (!menu) return null
  const { node, x, y } = menu
  const copy = () => {
    if (!node.url) return
    void navigator.clipboard.writeText(new URL(node.url, window.location.origin).href).then(() => setCopied(true))
  }
  return (
    <div
      ref={ref}
      role="menu"
      className="fixed z-50 min-w-[160px] rounded-lg border border-line bg-paper p-1 shadow"
      style={{ left: x, top: y }}
      data-testid="canvas-menu"
      data-seq={node.asset_seq}
    >
      <button type="button" className={item} onClick={() => onOpen(node)} data-testid="canvas-menu-open">
        <Maximize2 size={14} /> Open
      </button>
      {node.url && (
        <a href={node.url} download className={item} data-testid="canvas-menu-download">
          <Download size={14} /> Download
        </a>
      )}
      {node.url && (
        <button type="button" className={item} onClick={copy} data-testid="canvas-menu-copy">
          <Copy size={14} /> {copied ? 'copied' : 'Copy URL'}
        </button>
      )}
      <button type="button" className={item} onClick={() => navigate(`/assets/${node.asset_seq}`)} data-testid="canvas-menu-edit">
        <Pencil size={14} /> Edit
      </button>
    </div>
  )
}
