import type { Page } from '@playwright/test'
import { NOW, expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

const STALE = new Date(NOW.getTime() - 2 * 3_600_000).toISOString()

const SYNCED = { ok: 1, failed: 0, rows_written: 0, results: [] }

const answer = (page: Page, url: string, body: unknown, status = 200) =>
  page.route(url, async (r) => {
    await new Promise((resolve) => setTimeout(resolve, 300))
    await r.fulfill({ status, json: body })
  })

async function mockSync(page: Page, onAnswer = () => {}) {
  const request: { body?: unknown } = {}
  await page.route('**/api/sync', async (r) => {
    request.body = r.request().postDataJSON()
    await new Promise((resolve) => setTimeout(resolve, 300))
    onAnswer()
    await r.fulfill({ json: SYNCED })
  })
  await answer(page, '**/api/rebuild', { ok: true })
  return request
}

test('shows the last sync', async ({ page }) => {
  await visit(page, '/overview')
  await expect(page.getByTestId('sync-banner')).toBeVisible()
  await expect(page.getByTestId('sync-banner-text')).toHaveText(/^Last sync: .+\.$/)
  await expect(page.getByTestId('sync-now')).toHaveText('Sync now')
  await ready(page)
  await snap(page, 'dashboard-sync-banner')
})

test('sync now syncs then rebuilds', async ({ page }) => {
  let synced = false
  await page.route('**/api/sources', (r) => {
    const last_success = synced ? NOW.toISOString() : STALE
    return r.fulfill({ json: { sources: [{ source: 'google_analytics', category: 'Analytics', last_attempt: last_success, last_success }] } })
  })
  const request = await mockSync(page, () => (synced = true))
  await visit(page, '/overview')
  await expect(page.getByTestId('sync-banner-text')).toHaveText('Last sync: 2 hours ago.')
  const button = page.getByTestId('sync-now')
  await button.click()
  await expect(button).toHaveText('Syncing…')
  await expect(button).toHaveAttribute('aria-busy', 'true')
  await expect(button).toHaveText('Sync now')
  await expect(button).toBeEnabled()
  await expect(page.getByTestId('sync-banner-text')).toHaveText('Last sync: just now.')
  const { sources } = request.body as { sources: string[] }
  expect(sources.length).toBeGreaterThan(0)
  expect(sources).toContain('google_analytics')
})

test('google ads sub-tab syncs its own sources', async ({ page }) => {
  const request = await mockSync(page)
  await visit(page, '/ads/google_ads')
  await page.getByTestId('sync-now').click()
  await expect.poll(() => request.body).toEqual({ sources: ['google_ads', 'meta'] })
  await expect(page.getByTestId('sync-now')).toHaveText('Sync now')
})

test('attention syncs every source', async ({ page }) => {
  const request = await mockSync(page)
  await visit(page, '/attention')
  await page.getByTestId('sync-now').click()
  await expect.poll(() => request.body).toEqual({})
  await expect(page.getByTestId('sync-now')).toHaveText('Sync now')
})

test('sync failure', async ({ page }) => {
  await answer(page, '**/api/sync', SYNCED)
  await answer(page, '**/api/rebuild', { detail: 'a rebuild is already in progress' }, 409)
  await visit(page, '/overview')
  await page.getByTestId('sync-now').click()
  await expect(page.getByTestId('sync-banner-text')).toHaveText('Sync failed: a rebuild is already in progress')
  await expect(page.getByTestId('sync-banner')).toHaveClass(/bg-amber-50/)
  await expect(page.getByTestId('sync-now')).toBeEnabled()
})
