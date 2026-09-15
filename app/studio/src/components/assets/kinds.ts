import type { Kind } from '@/api'

export const KINDS: Kind[] = ['post', 'newsletter', 'blog', 'image', 'video', 'ad']

const GLYPHS: Record<Kind, string> = {
  post: 'in',
  newsletter: '✉',
  blog: 'blog',
  image: '▣',
  video: '▶',
  ad: '▣',
}

export const kindGlyph = (kind: Kind) => GLYPHS[kind]

export const mcpTool = (kind: Kind) => `dw.${kind}`
