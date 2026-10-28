import { Link } from 'react-router-dom'
import { Empty } from '@/components/ui/empty'

export function NoSuchApp({ name }: { name: string }) {
  return (
    <Empty testId="no-such-app">
      No app named {name}.{' '}
      <Link to="/" className="text-ink underline-offset-4 hover:underline">
        All apps
      </Link>
    </Empty>
  )
}
