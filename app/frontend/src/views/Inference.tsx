import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Ask } from './inference/Ask'
import { Coaching } from './inference/Coaching'
import { Enrichment } from './inference/Enrichment'

const keep = 'data-[state=inactive]:hidden'

export function Inference() {
  return (
    <Tabs defaultValue="enrichment">
      <TabsList>
        <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
        <TabsTrigger value="coaching">Coaching</TabsTrigger>
        <TabsTrigger value="ask">Ask</TabsTrigger>
      </TabsList>
      <TabsContent value="enrichment" forceMount className={keep}>
        <Enrichment />
      </TabsContent>
      <TabsContent value="coaching" forceMount className={keep}>
        <Coaching />
      </TabsContent>
      <TabsContent value="ask" forceMount className={keep}>
        <Ask />
      </TabsContent>
    </Tabs>
  )
}
