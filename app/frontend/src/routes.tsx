import type { ComponentType } from 'react'
import { Activity as ActivityIcon, Boxes, ChartColumn, Home, Map as MapIcon, Settings, Sparkles, type LucideIcon } from 'lucide-react'
import { Insights } from './views/Insights'
import { Activity } from './views/Activity'
import { Metrics } from './views/Metrics'
import { Entities } from './views/Entities'
import { Inference } from './views/Inference'
import { MapView } from './views/Map'
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
    to: '/inference',
    label: 'Inference',
    icon: Sparkles,
    title: 'Inference',
    view: Inference,
  },
  {
    to: '/map',
    label: 'Map',
    icon: MapIcon,
    title: 'Map',
    view: MapView,
  },
  {
    to: '/config',
    label: 'Config',
    icon: Settings,
    title: 'Config',
    view: Config,
  },
]
