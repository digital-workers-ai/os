import { useMemo, useState, type ReactNode } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, get } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  GraphControls,
  KnowledgeGraph,
  graphSummary,
  scopeGraph,
  type GraphResponse,
  type GraphView,
} from './visualize/KnowledgeGraph'
import { OntologyGraph, type OntologyResponse } from './visualize/OntologyGraph'

type Tab = 'graph' | 'ontology'

function Loaded<T>({ query, children }: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (query.data) return <>{children(query.data)}</>
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  return <Loading />
}

export function Visualize() {
  const [tab, setTab] = useState<Tab>('graph')
  const [view, setView] = useState<GraphView>({ typeFilter: 'all', hidden: new Set(), focus: null })
  const graph = useQuery({ queryKey: ['graph'], queryFn: () => get<GraphResponse>('/api/graph') })
  const ontology = useQuery({
    queryKey: ['ontology'],
    queryFn: () => get<OntologyResponse>('/api/knowledge/ontology'),
  })
  const scope = useMemo(
    () => (graph.data ? scopeGraph(graph.data, view) : null),
    [graph.data, view.typeFilter, view.hidden],
  )
  const graphHeader = tab === 'graph' && graph.data && scope ? { data: graph.data, scope } : null

  return (
    <SectionCard
      title="Visualize"
      description={graphHeader ? graphSummary(graphHeader.scope) : undefined}
      headerRight={
        graphHeader ? (
          <GraphControls counts={graphHeader.data.counts} scope={graphHeader.scope} view={view} onChange={setView} />
        ) : undefined
      }
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="graph">Knowledge graph</TabsTrigger>
          <TabsTrigger value="ontology">Ontology</TabsTrigger>
        </TabsList>
        <TabsContent value="graph">
          <Loaded query={graph}>
            {(data) => <KnowledgeGraph data={data} scope={scope ?? scopeGraph(data, view)} view={view} onChange={setView} />}
          </Loaded>
        </TabsContent>
        <TabsContent value="ontology">
          <Loaded query={ontology}>{(data) => <OntologyGraph data={data} />}</Loaded>
        </TabsContent>
      </Tabs>
    </SectionCard>
  )
}
