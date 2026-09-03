import { useEffect, useState } from 'react'
import { api, asApiError, type Health } from './api'
import { Estate } from './views/Estate'
import { Entities } from './views/Entities'
import { Metrics } from './views/Metrics'
import { Insights } from './views/Insights'
import { Inference } from './views/Inference'
import { Knowledge } from './views/Knowledge'

const ROUTES = [
  { path: 'estate', label: 'Estate', view: Estate },
  { path: 'entities', label: 'Entities', view: Entities },
  { path: 'metrics', label: 'Metrics', view: Metrics },
  { path: 'insights', label: 'Insights', view: Insights },
  { path: 'inference', label: 'Inference', view: Inference },
  { path: 'knowledge', label: 'Knowledge', view: Knowledge },
]

const current = () => window.location.hash.replace(/^#\/?/, '') || ROUTES[0].path

function useHashRoute() {
  const [path, setPath] = useState(current)
  useEffect(() => {
    const onChange = () => setPath(current())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return path
}

export default function App() {
  const path = useHashRoute()
  const route = ROUTES.find((r) => r.path === path) ?? ROUTES[0]
  const [health, setHealth] = useState<Health | null>(null)
  const [down, setDown] = useState<string | null>(null)

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h)
        setDown(null)
      })
      .catch((e) => setDown(asApiError(e).detail))
  }, [path])

  const View = route.view

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">OS v0</div>
        <nav className="tabs">
          {ROUTES.map((r) => (
            <a key={r.path} className="tab" href={`#/${r.path}`} aria-current={r === route ? 'page' : undefined}>
              {r.label}
            </a>
          ))}
        </nav>
        <div className="topbar-right">
          {down ? (
            <span className="pill err" title={down}>
              backend unreachable
            </span>
          ) : health ? (
            <span className={'pill ' + (health.status === 'ok' ? 'ok' : 'warn')}>health {health.status}</span>
          ) : (
            <span className="dim">connecting…</span>
          )}
        </div>
      </header>
      <main className="content">
        <View />
      </main>
    </div>
  )
}
