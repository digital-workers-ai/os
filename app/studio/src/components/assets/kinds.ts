import type { Kind } from '@/api'

export const KINDS: Kind[] = ['post', 'newsletter', 'blog', 'image', 'ad']

const GLYPHS: Record<Kind, string> = {
  post: 'in',
  newsletter: '✉',
  blog: 'blog',
  image: '▣',
  ad: '▣',
}

export const kindGlyph = (kind: Kind) => GLYPHS[kind]

export const mcpTool = (kind: Kind) => `dw.${kind}`
