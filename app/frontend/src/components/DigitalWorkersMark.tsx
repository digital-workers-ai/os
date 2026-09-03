export function DigitalWorkersMark({ className = '', size = 'sm' }: { className?: string; size?: 'sm' | 'md' }) {
  const text = size === 'md' ? 'text-[15px]' : 'text-[12px]'
  const dot = size === 'md' ? 'w-[7px] h-[7px]' : 'w-1.5 h-1.5'
  return (
    <span className={`inline-flex items-center gap-1.5 shrink-0 ${className}`}>
      <span
        className={`font-logo ${text} font-medium text-dbb-charcoal whitespace-nowrap leading-none`}
        style={{ letterSpacing: '0.016em' }}
      >
        Digital Workers
      </span>
      <span className={`${dot} rounded-full bg-dbb-forest shrink-0`} aria-hidden />
    </span>
  )
}
