import type { PostCompany } from '@/api'
import { Stat } from '@/cards/Stat'
import { Card, CardTitle } from '@/components/ui/card'

export function CompanySummary({ company }: { company: PostCompany }) {
  return (
    <Card className="p-4 sm:p-4" data-testid="posts-company" data-company={company.name}>
      <CardTitle className="truncate text-sm" title={company.name}>
        {company.name}
      </CardTitle>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <Stat n={company.posts} label="posts" />
        <Stat n={company.likes} label="likes" />
        <Stat n={company.comments} label="comments" />
      </div>
    </Card>
  )
}
