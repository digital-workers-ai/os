import type { ComponentType } from 'react'
import {
  Activity as ActivityIcon,
  BookOpen,
  Boxes,
  ChartColumn,
  Home,
  Search as SearchIcon,
  Settings,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { PATH, TAB } from './paths'
import { Insights } from './views/Insights'
import { Activity } from './views/Activity'
import { Metrics } from './views/Metrics'
import { Entities } from './views/Entities'
import { AI } from './views/AI'
import { Definitions } from './views/Definitions'
import { Config } from './views/Config'
import { Search } from './views/Search'

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
  to: PATH.entities,
  label: 'Entities',
  icon: Boxes,
  title: 'Entities',
  view: Entities,
  tabs: [
    { value: TAB.entities.canonical, label: 'Canonical' },
    { value: TAB.entities.raw, label: 'Raw entities' },
    { value: TAB.entities.visualize, label: 'Visualize' },
    { value: TAB.entities.review, label: 'Review' },
  ],
}

export const AI_ROUTE: TabbedRoute = {
  to: PATH.ai,
  label: 'AI',
  icon: Sparkles,
  title: 'AI',
  view: AI,
  tabs: [
    { value: TAB.ai.enrichment, label: 'Enrichment' },
    { value: TAB.ai.coaching, label: 'Coaching' },
  ],
}

export const DEFINITIONS_ROUTE: TabbedRoute = {
  to: PATH.definitions,
  label: 'Definitions',
  icon: BookOpen,
  title: 'Definitions',
  view: Definitions,
  tabs: [
    { value: TAB.definitions.ontology, label: 'Ontology' },
    { value: TAB.definitions.mappings, label: 'Mappings' },
    { value: TAB.definitions.transforms, label: 'Transforms' },
    { value: TAB.definitions.metrics, label: 'Metrics' },
    { value: TAB.definitions.derived, label: 'Derived' },
    { value: TAB.definitions.rules, label: 'Rules' },
    { value: TAB.definitions.goals, label: 'Goals' },
    { value: TAB.definitions.enrichment, label: 'Enrichment' },
    { value: TAB.definitions.dashboards, label: 'Dashboards' },
  ],
}

export const CONFIG_ROUTE: TabbedRoute = {
  to: PATH.config,
  label: 'Config',
  icon: Settings,
  title: 'Config',
  view: Config,
  tabs: [
    { value: TAB.config.sources, label: 'Sources' },
    { value: TAB.config.rebuild, label: 'Rebuild' },
    { value: TAB.config.mcp, label: 'MCP' },
  ],
}

export const SEARCH_ROUTE: RouteDef = {
  to: PATH.search,
  label: 'Search',
  icon: SearchIcon,
  title: 'Search',
  view: Search,
}

export const ROUTES: RouteDef[] = [
  {
    to: PATH.home,
    label: 'Home',
    icon: Home,
    end: true,
    title: 'Insights',
    view: Insights,
  },
  {
    to: PATH.activity,
    label: 'Activity',
    icon: ActivityIcon,
    title: 'Activity',
    view: Activity,
  },
  {
    to: PATH.metrics,
    label: 'Metrics',
    icon: ChartColumn,
    title: 'Metrics',
    view: Metrics,
  },
  ENTITIES_ROUTE,
  AI_ROUTE,
  DEFINITIONS_ROUTE,
  CONFIG_ROUTE,
  SEARCH_ROUTE,
]
