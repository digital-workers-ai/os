import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

const PAGE = 20

const option = (page: Page, company: string) => page.locator(`[data-testid="posts-filter-option"][data-company="${company}"]`)

const outside = (page: Page, platform: string) => page.locator(`[data-testid="post-row"]:not([data-platform="${platform}"])`)

const onlyPlatform = async (page: Page, platform: string) => {
  const rows = page.getByTestId('post-row')
  await expect(rows.first()).toHaveAttribute('data-platform', platform)
  await expect(outside(page, platform)).toHaveCount(0)
  for (const row of await rows.all()) await expect(row).toHaveAttribute('data-platform', platform)
}

test('posts', async ({ page }) => {
  const first = page.waitForResponse((r) => r.url().includes('/api/spy/posts?'))
  await visit(page, '/posts')
  const { companies, total } = await (await first).json()
  await expect(page.getByTestId('sub-nav').locator('a')).toHaveCount(4)
  await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
  await expect(page.getByTestId('posts-company')).toHaveCount(companies.length)
  const rows = page.getByTestId('post-row')
  await expect(rows).toHaveCount(Math.min(total, PAGE))
  await expect(rows.first()).toHaveAttribute('data-platform', /.+/)
  await expect(page.getByTestId('post-preview').first()).toBeVisible()
  await page.getByTestId('subnav-linkedin').click()
  await expect(page.getByTestId('subnav-linkedin')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveURL(/\/posts\/linkedin$/)
  await onlyPlatform(page, 'linkedin')
  await page.getByTestId('subnav-x').click()
  await expect(page.getByTestId('subnav-x')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveURL(/\/posts\/x$/)
  await onlyPlatform(page, 'x')
  await page.getByTestId('subnav-instagram').click()
  await expect(page.getByTestId('subnav-instagram')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveURL(/\/posts\/instagram$/)
  await onlyPlatform(page, 'instagram')
  await page.getByTestId('subnav-all').click()
  await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
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
