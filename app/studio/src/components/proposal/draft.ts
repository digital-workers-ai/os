import type { DraftFile, Kind, LookRow } from '@/api'

export type Shape = 'text' | 'video' | 'image'

export const shapeOf = (kind: Kind, look: LookRow | undefined): Shape => {
  if (kind === 'video') return 'video'
  if (kind === 'image') return 'image'
  if (kind === 'ad') return look?.medium === 'video' ? 'video' : 'image'
  return 'text'
}

const TEXT_FILE = /\.(md|txt|html|json|ya?ml)$/

const IMAGE_FILE = /\.(png|jpe?g|webp|svg)$/

export const mainDraft = (drafts: DraftFile[]) =>
  drafts.find((file) => file.media_type.startsWith('text/') || TEXT_FILE.test(file.path)) ?? drafts[0] ?? null

export const namedDraft = (drafts: DraftFile[], part: string) => drafts.find((file) => file.path.includes(part)) ?? null

export const imageDrafts = (drafts: DraftFile[]) => drafts.filter((file) => file.media_type.startsWith('image/') || IMAGE_FILE.test(file.path))

export const draftText = (file: DraftFile | null) => {
  const held = (file as { text?: unknown } | null)?.text
  return typeof held === 'string' && held !== '' ? held : null
}

export const bytesLabel = (bytes: number) => (bytes < 1024 ? `${bytes} B` : `${Math.round(bytes / 1024)} kB`)

export const shortSha = (sha: string) => sha.slice(0, 7)
