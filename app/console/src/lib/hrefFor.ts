import { PATH, TAB, tabPath } from '@/paths'
import { BRIEFING_REF_SEP, KIND, LINK } from '@/search/vocab'

const PAGES: Partial<Record<string, [string, string]>> = {
  [KIND.raw]: [tabPath('entities', TAB.entities.raw), LINK.event],
  [KIND.metric]: [PATH.metrics, LINK.metric],
  [KIND.rule]: [tabPath('definitions', TAB.definitions.rules), LINK.rule],
  [KIND.goal]: [tabPath('definitions', TAB.definitions.goals), LINK.goal],
  [KIND.source]: [tabPath('config', TAB.config.sources), LINK.source],
  [KIND.entityType]: [tabPath('definitions', TAB.definitions.ontology), LINK.type],
  [KIND.reading]: [tabPath('definitions', TAB.definitions.enrichment), LINK.reading],
}

export function hrefFor(kind: string, id: string): string {
  if (kind === KIND.briefing) {
    const [role, seq] = id.split(BRIEFING_REF_SEP)
    return `${tabPath('ai', TAB.ai.coaching)}?${LINK.role}=${encodeURIComponent(role)}&${LINK.briefing}=${encodeURIComponent(seq)}`
  }
  const [path, param] = PAGES[kind] ?? [tabPath('entities', TAB.entities.canonical), LINK.entity]
  return `${path}?${param}=${encodeURIComponent(id)}`
}
