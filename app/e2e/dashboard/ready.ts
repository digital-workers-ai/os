import type { Page } from '@playwright/test'
import { expect, settle } from '../fixtures'

export async function ready(page: Page) {
  await expect(page.getByTestId('loading')).toHaveCount(0, { timeout: 20_000 })
  await settle(page)
}
