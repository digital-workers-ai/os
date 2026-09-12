import { Banner } from '@/components/ui/banner'
import { consoleUrl } from '@/lib/console'

export function EmptyPage() {
  return (
    <Banner className="mb-6" testId="empty-page">
      No data for this page yet —{' '}
      <a href={consoleUrl('/config/sources')} className="underline" target="_blank" rel="noreferrer">
        connect sources in the Console
      </a>
    </Banner>
  )
}
