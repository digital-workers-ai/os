import type { ReactNode } from 'react'
import type { ApiError } from '@/api'
import { Mono } from '@/components/ui/mono'
import { cn } from '@/lib/utils'

const TONES = {
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  err: 'border-err/30 bg-err/5 text-err',
}

export function Banner({
  tone = 'warn',
  className,
  testId = 'banner',
  children,
}: {
  tone?: keyof typeof TONES
  className?: string
  testId?: string
  children: ReactNode
}) {
  return (
    <div
      role={tone === 'err' ? 'alert' : 'status'}
      className={cn('rounded-lg border px-3 py-2 text-sm', TONES[tone], className)}
      data-testid={testId}
    >
      {children}
    </div>
  )
}

export function ErrorBanner({ error, className, testId = 'error-banner' }: { error: ApiError | null; className?: string; testId?: string }) {
  if (!error) return null
  return (
    <Banner tone="err" className={className} testId={testId}>
      <Mono>{error.status || 'network'}</Mono> {error.detail}
    </Banner>
  )
}
