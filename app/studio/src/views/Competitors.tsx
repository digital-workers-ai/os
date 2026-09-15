import type { ComponentType } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { SubNav } from '@/components/TopNav'
import { AdsPanel } from '@/components/competitors/Ads'
import { AnswersPanel } from '@/components/competitors/Answers'
import { CompaniesPanel } from '@/components/competitors/Companies'
import { ContentPanel } from '@/components/competitors/Content'
import { SearchPanel } from '@/components/competitors/Search'
import { SwipeFile } from '@/components/competitors/SwipeFile'

const TABS: [string, string][] = [
  ['swipe', 'Swipe file'],
  ['ads', 'Ads'],
  ['search', 'Search'],
  ['answers', 'AI answers'],
  ['content', 'Content'],
  ['companies', 'Companies'],
]

const PANELS: Record<string, ComponentType> = {
  swipe: SwipeFile,
  ads: AdsPanel,
  search: SearchPanel,
  answers: AnswersPanel,
  content: ContentPanel,
  companies: CompaniesPanel,
}

export function Competitors() {
  const { tab = '' } = useParams()
  const Panel = PANELS[tab]
  if (!Panel) return <Navigate to="/competitors/swipe" replace />
  return (
    <div className="space-y-4" data-testid="competitors-view" data-tab={tab}>
      <SubNav base="/competitors" tabs={TABS} current={tab} />
      <Panel />
    </div>
  )
}
