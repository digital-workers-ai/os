import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function NewAppLink() {
  return (
    <Button asChild variant="solid" className="ml-auto">
      <Link to="/new">
        <Plus aria-hidden />
        New app
      </Link>
    </Button>
  )
}
