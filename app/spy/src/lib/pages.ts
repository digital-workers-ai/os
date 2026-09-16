export interface PageSpec {
  value: string
  label: string
  ranged: boolean
}

export const PAGES: PageSpec[] = [
  { value: 'overview', label: 'Overview', ranged: true },
  { value: 'visibility', label: 'Visibility', ranged: true },
  { value: 'ads', label: 'Ads', ranged: true },
  { value: 'posts', label: 'Posts', ranged: true },
  { value: 'competitors', label: 'Competitors', ranged: false },
]

export const FIRST = PAGES[0].value

export const isRanged = (page?: string) => PAGES.some((spec) => spec.value === page && spec.ranged)
