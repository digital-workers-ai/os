import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function SectionCard({
  title,
  headerRight,
  className,
  children,
}: {
  title?: ReactNode
  headerRight?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={className}>
      {(title || headerRight) && (
        <CardHeader>
          {title && <CardTitle>{title}</CardTitle>}
          {headerRight && <div className="shrink-0">{headerRight}</div>}
        </CardHeader>
      )}
      <CardContent>{children}</CardContent>
    </Card>
  )
}
