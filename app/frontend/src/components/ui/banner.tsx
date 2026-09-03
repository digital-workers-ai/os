import type { ReactNode } from 'react'
import type { ApiError } from '@/api'
import { Mono } from '@/components/ui/mono'
import { cn } from '@/lib/utils'

const TONES = {
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  err: 'border-dbb-clay/30 bg-dbb-clay/5 text-dbb-clay',
}

export function Banner({ tone = 'warn', className, children }: { tone?: keyof typeof TONES; className?: string; children: ReactNode }) {
  return (
    <div role={tone === 'err' ? 'alert' : 'status'} className={cn('rounded-lg border px-3 py-2 text-sm', TONES[tone], className)}>
      {children}
    </div>
  )
}

export function ErrorBanner({ error, className }: { error: ApiError | null; className?: string }) {
  if (!error) return null
  return (
    <Banner tone="err" className={className}>
      <Mono>{error.status || 'network'}</Mono> {error.detail}
    </Banner>
  )
}
