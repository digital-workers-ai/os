export const PATH = { home: '/', activity: '/activity', metrics: '/metrics', entities: '/entities', ai: '/ai', definitions: '/definitions', config: '/config', search: '/search' } as const
export const TAB = {
  entities: { canonical: 'canonical', raw: 'raw', visualize: 'visualize', review: 'review' },
  ai: { enrichment: 'enrichment', coaching: 'coaching' },
  definitions: { ontology: 'ontology', mappings: 'mappings', transforms: 'transforms', metrics: 'metrics', derived: 'derived', rules: 'rules', goals: 'goals', enrichment: 'enrichment' },
  config: { sources: 'sources', rebuild: 'rebuild', mcp: 'mcp' },
} as const
export const tabPath = (page: keyof typeof TAB, tab: string) => `${PATH[page]}/${tab}`
