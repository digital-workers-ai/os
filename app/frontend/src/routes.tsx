import type { ComponentType } from 'react'
import { Activity as ActivityIcon, BookOpen, Boxes, ChartColumn, Home, Settings, Sparkles, type LucideIcon } from 'lucide-react'
import { Insights } from './views/Insights'
import { Activity } from './views/Activity'
import { Metrics } from './views/Metrics'
import { Entities } from './views/Entities'
import { AI } from './views/AI'
import { Definitions } from './views/Definitions'
import { Config } from './views/Config'

export interface RouteDef {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  title: string
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
  {
    to: '/entities',
    label: 'Entities',
    icon: Boxes,
    title: 'Entities',
    view: Entities,
  },
  {
    to: '/ai',
    label: 'AI',
    icon: Sparkles,
    title: 'AI',
    view: AI,
  },
  {
    to: '/definitions',
    label: 'Definitions',
    icon: BookOpen,
    title: 'Definitions',
    view: Definitions,
  },
  {
    to: '/config',
    label: 'Config',
    icon: Settings,
    title: 'Config',
    view: Config,
  },
]
