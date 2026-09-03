import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SectionCard({
  title,
  description,
  headerRight,
  className,
  children,
}: {
  title?: ReactNode
  description?: ReactNode
  headerRight?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={className}>
      {(title || description || headerRight) && (
        <CardHeader>
          <div className="min-w-0">
            {title && <CardTitle>{title}</CardTitle>}
            {description && <CardDescription className="mt-0.5">{description}</CardDescription>}
          </div>
          {headerRight && <div className="shrink-0">{headerRight}</div>}
        </CardHeader>
      )}
      <CardContent>{children}</CardContent>
    </Card>
  )
}
