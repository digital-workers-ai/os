import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

const PAGE = 20

const option = (page: Page, company: string) => page.locator(`[data-testid="posts-filter-option"][data-company="${company}"]`)

test('posts', async ({ page }) => {
  const first = page.waitForResponse((r) => r.url().includes('/api/spy/posts?'))
  await visit(page, '/posts')
  const { companies, total } = await (await first).json()
  await expect(page.getByTestId('posts-company')).toHaveCount(companies.length)
  const rows = page.getByTestId('post-row')
  await expect(rows).toHaveCount(Math.min(total, PAGE))
  await expect(option(page, 'all')).toHaveAttribute('aria-pressed', 'true')
  const second = page.getByTestId('posts-filter-option').nth(1)
  const company = (await second.getAttribute('data-company'))!
  await second.click()
  await expect(second).toHaveAttribute('aria-pressed', 'true')
  await expect(rows.first()).toHaveAttribute('data-company', company)
  await expect(page.locator(`[data-testid="post-row"]:not([data-company="${company}"])`)).toHaveCount(0)
  await option(page, 'all').click()
  await expect(option(page, 'all')).toHaveAttribute('aria-pressed', 'true')
  await expect(rows).toHaveCount(Math.min(total, PAGE))
  await ready(page)
  await snap(page, 'spy-posts')
})
