import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

const PAGE = 20

const option = (page: Page, company: string) => page.locator(`[data-testid="posts-filter-option"][data-company="${company}"]`)

test('posts', async ({ page }) => {
  const first = page.waitForResponse((r) => r.url().includes('/api/spy/posts?'))
  await visit(page, '/posts')
  const { companies, total } = await (await first).json()
  await expect(page.getByTestId('sub-nav').locator('a')).toHaveCount(3)
  await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
  await expect(page.getByTestId('posts-company')).toHaveCount(companies.length)
  const rows = page.getByTestId('post-row')
  const notLinkedin = page.locator('[data-testid="post-row"]:not([data-platform="linkedin"])')
  const notX = page.locator('[data-testid="post-row"]:not([data-platform="x"])')
  await expect(rows).toHaveCount(Math.min(total, PAGE))
  await expect(rows.first()).toHaveAttribute('data-platform', 'linkedin')
  await expect(notLinkedin).toHaveCount(0)
  await expect(page.getByTestId('post-preview').first()).toBeVisible()
  await page.getByTestId('subnav-linkedin').click()
  await expect(page.getByTestId('subnav-linkedin')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveURL(/\/posts\/linkedin$/)
  await expect(rows.first()).toHaveAttribute('data-platform', 'linkedin')
  await expect(notLinkedin).toHaveCount(0)
  await page.getByTestId('subnav-x').click()
  await expect(page.getByTestId('subnav-x')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveURL(/\/posts\/x$/)
  await expect(rows.first()).toHaveAttribute('data-platform', 'x')
  await expect(notX).toHaveCount(0)
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
