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
  description?: string
  view: ComponentType
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
    to: '/metrics',
    label: 'Metrics',
    icon: ChartColumn,
    title: 'Metrics',
    description: 'click a metric to open its series',
    view: Metrics,
  },
  {
    to: '/entities',
    label: 'Entities',
    icon: Boxes,
    title: 'Entities',
    view: Entities,
  },
  {
    to: '/inference',
    label: 'Inference',
    icon: Sparkles,
    title: 'Inference',
    view: Inference,
  },
  {
    to: '/knowledge',
    label: 'Knowledge',
    icon: BookOpen,
    title: 'Knowledge',
    view: Knowledge,
  },
  {
    to: '/estate',
    label: 'Estate',
    icon: Database,
    title: 'Estate',
    view: Estate,
  },
  {
    to: '/visualize',
    label: 'Visualize',
    icon: ChartLine,
    title: 'Visualize',
    view: Visualize,
  },
]
