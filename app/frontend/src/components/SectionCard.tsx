import type { ReactNode, Ref } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SectionCard({
  title,
  description,
  headerRight,
  className,
  bodyClassName,
  bodyRef,
  testId,
  children,
}: {
  title?: ReactNode
  description?: ReactNode
  headerRight?: ReactNode
  className?: string
  bodyClassName?: string
  bodyRef?: Ref<HTMLDivElement>
  testId?: string
  children: ReactNode
}) {
  const part = (suffix: string) => testId && `${testId}-${suffix}`
  return (
    <Card className={className} data-testid={testId}>
      {(title || description || headerRight) && (
        <CardHeader className="shrink-0 flex-col items-stretch gap-0">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0" data-testid={part('title')}>
              {title && <CardTitle>{title}</CardTitle>}
            </div>
            {headerRight && (
              <div className="shrink-0" data-testid={part('actions')}>
                {headerRight}
              </div>
            )}
          </div>
          {description && (
            <CardDescription className="mt-0.5" data-testid={part('description')}>
              {description}
            </CardDescription>
          )}
        </CardHeader>
      )}
      <CardContent ref={bodyRef} className={bodyClassName} data-testid={part('body')}>
        {children}
      </CardContent>
    </Card>
  )
}
