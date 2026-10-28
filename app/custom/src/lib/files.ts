import type { Sent } from '@/api'

const LONG_EDGE = 2576
const QUALITY = 0.85
const HEIC = /\.(heic|heif)$/i

const HEIC_MESSAGE =
  "This browser can't open HEIC photos. Take the photo again from here, or set the iPhone camera to Most Compatible."

export function base64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

const isHeic = (file: File) => file.type === 'image/heic' || file.type === 'image/heif' || HEIC.test(file.name)

function unreadable(file: File): Error {
  return new Error(isHeic(file) ? HEIC_MESSAGE : `${file.name || 'This file'} is not a photo this browser can open.`)
}

async function drawn(file: File): Promise<HTMLCanvasElement> {
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode().catch(() => {
      throw unreadable(file)
    })
    const scale = Math.min(1, LONG_EDGE / Math.max(image.naturalWidth, image.naturalHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(image.naturalWidth * scale)
    canvas.height = Math.round(image.naturalHeight * scale)
    canvas.getContext('2d')!.drawImage(image, 0, 0, canvas.width, canvas.height)
    return canvas
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function jpeg(file: File, name: string): Promise<Sent> {
  const canvas = await drawn(file)
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
  if (!blob) throw unreadable(file)
  return { name, media_type: 'image/jpeg', data: await base64(blob) }
}

export const stem = (path: string) => path.replace(/\.[^.]*$/, '')
