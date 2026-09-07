import type { ComponentType } from 'react'
import { Activity as ActivityIcon, BookOpen, Boxes, ChartColumn, Home, Settings, Sparkles, type LucideIcon } from 'lucide-react'
import { Insights } from './views/Insights'
import { Activity } from './views/Activity'
import { Metrics } from './views/Metrics'
import { Entities } from './views/Entities'
import { AI } from './views/AI'
import { Definitions } from './views/Definitions'
import { Config } from './views/Config'

export interface TabDef {
  value: string
  label: string
}

export interface RouteDef {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  title: string
  view: ComponentType
  tabs?: TabDef[]
}

export interface TabbedRoute extends RouteDef {
  tabs: TabDef[]
}

export const ENTITIES_ROUTE: TabbedRoute = {
  to: '/entities',
  label: 'Entities',
  icon: Boxes,
  title: 'Entities',
  view: Entities,
  tabs: [
    { value: 'canonical', label: 'Canonical' },
    { value: 'raw', label: 'Raw entities' },
    { value: 'visualize', label: 'Visualize' },
  ],
}

export const AI_ROUTE: TabbedRoute = {
  to: '/ai',
  label: 'AI',
  icon: Sparkles,
  title: 'AI',
  view: AI,
  tabs: [
    { value: 'enrichment', label: 'Enrichment' },
    { value: 'coaching', label: 'Coaching' },
  ],
}

export const DEFINITIONS_ROUTE: TabbedRoute = {
  to: '/definitions',
  label: 'Definitions',
  icon: BookOpen,
  title: 'Definitions',
  view: Definitions,
  tabs: [
    { value: 'ontology', label: 'Ontology' },
    { value: 'mappings', label: 'Mappings' },
    { value: 'transforms', label: 'Transforms' },
    { value: 'metrics', label: 'Metrics' },
    { value: 'rules', label: 'Rules' },
    { value: 'goals', label: 'Goals' },
    { value: 'enrichment', label: 'Enrichment' },
  ],
}

export const CONFIG_ROUTE: TabbedRoute = {
  to: '/config',
  label: 'Config',
  icon: Settings,
  title: 'Config',
  view: Config,
  tabs: [
    { value: 'sources', label: 'Sources' },
    { value: 'rebuild', label: 'Rebuild' },
    { value: 'mcp', label: 'MCP' },
  ],
}

export const ROUTES: RouteDef[] = [
  {
    to: '/',
    label: 'Home',
    icon: Home,
    end: true,
    title: 'Insights',
    view: Insights,
  },
  {
    to: '/activity',
    label: 'Activity',
    icon: ActivityIcon,
    title: 'Activity',
    view: Activity,
  },
  {
    to: '/metrics',
    label: 'Metrics',
    icon: ChartColumn,
    title: 'Metrics',
    view: Metrics,
  },
  ENTITIES_ROUTE,
  AI_ROUTE,
  DEFINITIONS_ROUTE,
  CONFIG_ROUTE,
]
