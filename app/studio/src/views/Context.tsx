import type { ComponentType } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { SubNav } from '@/components/TopNav'
import { BrandPanel } from '@/components/context/Brand'
import { LooksPanel } from '@/components/context/Looks'
import { McpPanel } from '@/components/context/Mcp'
import { SkillsPanel } from '@/components/context/Skills'
import { SourcesPanel } from '@/components/context/Sources'

const TABS: [string, string][] = [
  ['brand', 'Brand'],
  ['skills', 'Skills'],
  ['looks', 'Looks'],
  ['sources', 'Sources'],
  ['mcp', 'MCP'],
]

const PANELS: Record<string, ComponentType> = {
  brand: BrandPanel,
  skills: SkillsPanel,
  looks: LooksPanel,
  sources: SourcesPanel,
  mcp: McpPanel,
}

export function Context() {
  const { tab = '' } = useParams()
  const Panel = PANELS[tab]
  if (!Panel) return <Navigate to="/context/brand" replace />
  return (
    <div className="space-y-4" data-testid="context-view" data-tab={tab}>
      <SubNav base="/context" tabs={TABS} current={tab} />
      <Panel />
    </div>
  )
}
