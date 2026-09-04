import { useCallback, useState, type ReactNode } from 'react'
import { usePageBadge } from '@/components/PageHeader'
import { Banner } from '@/components/ui/banner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Coaching } from './inference/Coaching'
import { Enrichment } from './inference/Enrichment'
import { PAGE_FILL } from './inference/shared'

type Tab = 'enrichment' | 'coaching'
type Flag = boolean | null

const keep = 'lg:min-h-0 lg:flex-1 data-[state=inactive]:hidden'

function Gate({ flag, children }: { flag: Flag; children: ReactNode }) {
  const off = flag === false
  return (
    <div className={off ? 'lg:h-full cursor-not-allowed' : 'lg:h-full'}>
      <div className={off ? 'lg:h-full opacity-50 pointer-events-none select-none' : 'lg:h-full'}>{children}</div>
    </div>
  )
}

export function AI() {
  const [tab, setTab] = useState<Tab>('enrichment')
  const [flags, setFlags] = useState<Record<Tab, Flag>>({ enrichment: null, coaching: null })
  const onEnrichment = useCallback((on: boolean) => setFlags((f) => ({ ...f, enrichment: on })), [])
  const onCoaching = useCallback((on: boolean) => setFlags((f) => ({ ...f, coaching: on })), [])
  const flag = flags[tab]
  usePageBadge(
    flag === false ? <Banner className="inline-flex items-center px-3 py-0.5">disabled · switched off in settings</Banner> : null,
  )

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
        <TabsTrigger value="coaching">Coaching</TabsTrigger>
      </TabsList>
      <TabsContent value="enrichment" forceMount className={keep}>
        <Gate flag={flags.enrichment}>
          <Enrichment onEnabled={onEnrichment} />
        </Gate>
      </TabsContent>
      <TabsContent value="coaching" forceMount className={keep}>
        <Gate flag={flags.coaching}>
          <Coaching onEnabled={onCoaching} />
        </Gate>
      </TabsContent>
    </Tabs>
  )
}
