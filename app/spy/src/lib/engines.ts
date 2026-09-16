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

export const PLATFORMS: Option[] = [{ value: 'google', label: 'Google' }]

export const known = (options: Option[], value?: string) => value === undefined || options.some((option) => option.value === value)
