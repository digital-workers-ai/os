import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Coaching } from './inference/Coaching'
import { Enrichment } from './inference/Enrichment'
import { PAGE_FILL } from './inference/shared'

const keep = 'lg:min-h-0 lg:flex-1 data-[state=inactive]:hidden'

export function AI() {
  return (
    <Tabs defaultValue="enrichment" className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
        <TabsTrigger value="coaching">Coaching</TabsTrigger>
      </TabsList>
      <TabsContent value="enrichment" forceMount className={keep}>
        <Enrichment />
      </TabsContent>
      <TabsContent value="coaching" forceMount className={keep}>
        <Coaching />
      </TabsContent>
    </Tabs>
  )
}
