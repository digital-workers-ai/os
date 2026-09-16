import type { Post } from '@/api'
import { Stat } from '@/cards/Stat'
import { shortDate } from '@/lib/format'

export function PostRow({ post }: { post: Post }) {
  return (
    <li className="flex items-start gap-3 border-b border-line/30 py-2 text-sm last:border-0" data-testid="post-row" data-company={post.company}>
      <span className="w-14 shrink-0 whitespace-nowrap tabular-nums text-muted">{shortDate(post.posted_at.slice(0, 10))}</span>
      <span className="w-28 shrink-0 truncate font-medium text-ink" title={post.company}>
        {post.company}
      </span>
      <span className="line-clamp-2 min-w-0 flex-1 text-ink" title={post.name}>
        {post.name}
      </span>
      <Stat n={post.likes} label="likes" className="w-20 shrink-0 text-right" />
      <Stat n={post.comments} label="comments" className="w-28 shrink-0 text-right" />
      <a href={post.url} target="_blank" rel="noreferrer" className="shrink-0 text-muted underline-offset-4 hover:text-ink hover:underline">
        View
      </a>
    </li>
  )
}
