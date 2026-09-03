import { useState, type ReactNode } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, get } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { GraphControls, KnowledgeGraph, type GraphResponse, type GraphView } from './visualize/KnowledgeGraph'
import { OntologyGraph, type OntologyResponse } from './visualize/OntologyGraph'

type Tab = 'graph' | 'ontology'

function Loaded<T>({ query, children }: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (query.data) return <>{children(query.data)}</>
  if (query.error) return <p className="text-sm text-dbb-down">{asApiError(query.error).detail}</p>
  return <p className="text-sm text-dbb-muted">Loading…</p>
}

export function Visualize() {
  const [tab, setTab] = useState<Tab>('graph')
  const [view, setView] = useState<GraphView>({ typeFilter: 'all', showIsolated: false, hidden: new Set(), seed: 1 })
  const graph = useQuery({ queryKey: ['graph'], queryFn: () => get<GraphResponse>('/api/graph') })
  const ontology = useQuery({
    queryKey: ['ontology'],
    queryFn: () => get<OntologyResponse>('/api/knowledge/ontology'),
  })

  return (
    <SectionCard
      title="Visualize"
      headerRight={tab === 'graph' && graph.data ? <GraphControls data={graph.data} view={view} onChange={setView} /> : undefined}
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="graph">Knowledge graph</TabsTrigger>
          <TabsTrigger value="ontology">Ontology</TabsTrigger>
        </TabsList>
        <TabsContent value="graph">
          <Loaded query={graph}>{(data) => <KnowledgeGraph data={data} view={view} onChange={setView} />}</Loaded>
        </TabsContent>
        <TabsContent value="ontology">
          <Loaded query={ontology}>{(data) => <OntologyGraph data={data} />}</Loaded>
        </TabsContent>
      </Tabs>
    </SectionCard>
  )
}
