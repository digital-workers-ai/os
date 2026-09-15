import { useEffect, useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getMcp, type McpResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { stamp } from '@/components/context/stamp'
import { num } from '@/lib/format'

type Tool = McpResponse['tools'][number]

const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'
const CHIP = 'inline-block rounded-full border border-line px-2 py-0.5 font-mono text-[11px] text-ink'

function ToolGroup({ label, tools }: { label: string; tools: Tool[] }) {
  if (tools.length === 0) return null
  return (
    <div>
      <p className={LABEL}>{label}</p>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {tools.map((tool) => (
          <span key={tool.name} title={tool.description} className={CHIP} data-testid="mcp-tool" data-name={tool.name}>
            {tool.name}
          </span>
        ))}
      </div>
    </div>
  )
}

function McpBody({ query }: { query: UseQueryResult<McpResponse> }) {
  const [copied, setCopied] = useState('')
  useEffect(() => {
    if (copied === '') return
    const timer = setTimeout(() => setCopied(''), 2000)
    return () => clearTimeout(timer)
  }, [copied])
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.tools.length === 0 && data.recent.length === 0) return <Empty>no tools served yet</Empty>
  const copy = (target: string) => {
    navigator.clipboard.writeText(JSON.stringify(data.config, null, 2)).then(
      () => setCopied(target),
      () => setCopied(''),
    )
  }
  return (
    <div className="space-y-3">
      <ToolGroup label="context tools" tools={data.tools.filter((tool) => tool.group === 'context')} />
      <div>
        <ToolGroup label="skill tools" tools={data.tools.filter((tool) => tool.group === 'skill')} />
        <p className="mt-1 text-xs text-muted">each runs the skill on the backend in chat mode</p>
      </div>
      <div data-testid="mcp-recent">
        <p className={LABEL}>recent</p>
        {data.recent.length === 0 ? (
          <Empty>no calls yet</Empty>
        ) : (
          <ul className="mt-1 divide-y divide-line/30">
            {data.recent.map((call) => (
              <li key={`${call.at}|${call.name}|${call.detail}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-1.5 text-sm">
                <span className="whitespace-nowrap text-muted">
                  {stamp(call.at)}
                </span>
                <span className="text-ink">{call.client}</span>
                <Mono className="text-muted">{call.name}</Mono>
                <span className="min-w-0 text-muted">{call.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => copy('claude-ai')} data-testid="mcp-copy-claude-ai">
          {copied === 'claude-ai' ? 'copied' : 'Copy config for Claude.ai'}
        </Button>
        <Button variant="outline" size="sm" onClick={() => copy('claude-code')} data-testid="mcp-copy-claude-code">
          {copied === 'claude-code' ? 'copied' : 'Copy config for Claude Code'}
        </Button>
      </div>
    </div>
  )
}

export function McpPanel() {
  const query = useQuery({ queryKey: ['mcp'], queryFn: getMcp })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="mcp-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
        <h2 className={LABEL}>MCP</h2>
        {data && (
          <span className="flex flex-wrap items-baseline gap-2 text-xs text-muted">
            <span data-testid="mcp-endpoint">
              <Mono className="text-ink">{data.endpoint}</Mono>
            </span>
            <span>· {num(data.tools.length)} tools</span>
            <span>· {num(data.calls_7d)} calls (7d)</span>
          </span>
        )}
      </div>
      <McpBody query={query} />
    </Card>
  )
}
