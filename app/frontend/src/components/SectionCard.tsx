import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SectionCard({
  title,
  description,
  headerRight,
  className,
  bodyClassName,
  children,
}: {
  title?: ReactNode
  description?: ReactNode
  headerRight?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <Card className={className}>
      {(title || description || headerRight) && (
        <CardHeader className="shrink-0 flex-col items-stretch gap-0">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">{title && <CardTitle>{title}</CardTitle>}</div>
            {headerRight && <div className="shrink-0">{headerRight}</div>}
          </div>
          {description && <CardDescription className="mt-0.5">{description}</CardDescription>}
        </CardHeader>
      )}
      <CardContent className={bodyClassName}>{children}</CardContent>
    </Card>
  )
}
