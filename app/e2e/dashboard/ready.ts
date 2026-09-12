import type { Page } from '@playwright/test'
import { expect, settle } from '../fixtures'

export interface CardSpec {
  shape: string
  metric?: string
  entity?: string
  rank?: string
}

export const cardId = (card: CardSpec) => (card.shape === 'table' ? `card-table-${card.entity}-${card.rank}` : `card-${card.metric}`)

export async function ready(page: Page) {
  await expect(page.locator('[data-state="loading"]')).toHaveCount(0, { timeout: 30_000 })
  await expect(page.getByTestId('loading')).toHaveCount(0, { timeout: 30_000 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await settle(page)
}
