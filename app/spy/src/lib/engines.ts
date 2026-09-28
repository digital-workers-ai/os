export interface Option {
  value: string
  label: string
}

export const ENGINES: Option[] = [
  { value: 'google', label: 'Google' },
  { value: 'ai_overview', label: 'AI Overviews' },
  { value: 'chatgpt', label: 'ChatGPT' },
  { value: 'perplexity', label: 'Perplexity' },
  { value: 'claude', label: 'Claude' },
  { value: 'gemini', label: 'Gemini' },
]

export const AD_PLATFORMS: Option[] = [
  { value: 'google', label: 'Google' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'meta', label: 'Meta' },
]

export const POST_PLATFORMS: Option[] = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'x', label: 'X' },
]

export const known = (options: Option[], value?: string) => value === undefined || options.some((option) => option.value === value)

export const platformLabel = (value: string) => [...AD_PLATFORMS, ...POST_PLATFORMS].find((option) => option.value === value)?.label ?? value
