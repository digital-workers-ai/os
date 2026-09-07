const PAGES: Partial<Record<string, [string, string]>> = {
  raw: ['/entities/raw', 'event'],
  metric: ['/metrics', 'metric'],
  rule: ['/definitions/rules', 'rule'],
  goal: ['/definitions/goals', 'goal'],
  source: ['/config/sources', 'source'],
  entity_type: ['/definitions/ontology', 'type'],
  reading: ['/definitions/enrichment', 'reading'],
}

export function hrefFor(kind: string, id: string): string {
  if (kind === 'briefing') {
    const [role, seq] = id.split('/')
    return `/ai/coaching?role=${encodeURIComponent(role)}&briefing=${encodeURIComponent(seq)}`
  }
  const [path, param] = PAGES[kind] ?? ['/entities/canonical', 'entity']
  return `${path}?${param}=${encodeURIComponent(id)}`
}
