import type { ComponentType } from 'react'
import { BookOpen, Boxes, ChartColumn, ChartLine, Database, Home, Sparkles, type LucideIcon } from 'lucide-react'
import { Insights } from './views/Insights'
import { Metrics } from './views/Metrics'
import { Entities } from './views/Entities'
import { Inference } from './views/Inference'
import { Knowledge } from './views/Knowledge'
import { Estate } from './views/Estate'
import { Visualize } from './views/Visualize'

export interface RouteDef {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  title: string
  subtitle: string
  view: ComponentType
  legacy?: boolean
}

export const ROUTES: RouteDef[] = [
  {
    to: '/',
    label: 'Home',
    icon: Home,
    end: true,
    title: 'Insights',
    subtitle: 'goals and findings over the canonical estate',
    view: Insights,
  },
  {
    to: '/metrics',
    label: 'Metrics',
    icon: ChartColumn,
    title: 'Metrics',
    subtitle: 'metric series and snapshots computed from the estate',
    view: Metrics,
  },
  {
    to: '/entities',
    label: 'Entities',
    icon: Boxes,
    title: 'Entities',
    subtitle: 'canonical entities and the raw records behind them',
    view: Entities,
  },
  {
    to: '/inference',
    label: 'Inference',
    icon: Sparkles,
    title: 'Inference',
    subtitle: 'ask, coaching, and enrichment over the estate',
    view: Inference,
  },
  {
    to: '/knowledge',
    label: 'Knowledge',
    icon: BookOpen,
    title: 'Knowledge',
    subtitle: 'the committed ontology, mappings, transforms, metrics, and vocabulary',
    view: Knowledge,
  },
  {
    to: '/estate',
    label: 'Estate',
    icon: Database,
    title: 'Estate',
    subtitle: 'sources, sync activity, rebuild, and the engine report',
    view: Estate,
  },
  {
    to: '/visualize',
    label: 'Visualize',
    icon: ChartLine,
    title: 'Visualize',
    subtitle: 'charts over the canonical estate',
    view: Visualize,
  },
]
