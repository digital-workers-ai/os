import type { Page } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { expect, settle } from '../fixtures'

export const PHOTO = fileURLToPath(new URL('./fixtures/receipt.jpg', import.meta.url))

export const NOT_COUNTED = 'Saved. Counts in the numbers after the next Rebuild'

const HOLD_MS = 1500

export interface Update {
  row?: string | number
  column?: string
  section?: string
  item?: string
  list?: string
  field: string
  value: unknown
}

export interface Heard {
  transcript: string
  updates: Update[]
  cursor: Record<string, unknown> | null
  readback: string
}

export interface Clip {
  audio: { media_type: string; data: string }
  cursor: Record<string, unknown> | null
}

export async function ready(page: Page) {
  await expect(page.getByTestId('page-main')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('[data-state="loading"]')).toHaveCount(0, { timeout: 30_000 })
  await expect(page.getByTestId('loading')).toHaveCount(0, { timeout: 30_000 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await settle(page)
}

export async function hearInTurn(page: Page, answers: Heard[]) {
  let next = 0
  await page.route('**/api/custom/records/*/hear', (r) => r.fulfill({ json: answers[Math.min(next++, answers.length - 1)] }))
}

export async function holdToTalk(page: Page): Promise<Clip> {
  const talk = page.getByTestId('talk')
  await talk.scrollIntoViewIfNeeded()
  const box = (await talk.boundingBox())!
  const heard = page.waitForRequest((r) => /\/api\/custom\/records\/[^/]+\/hear$/.test(r.url()) && r.method() === 'POST')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await expect(talk).toHaveAttribute('aria-pressed', 'true')
  await page.waitForTimeout(HOLD_MS)
  await page.mouse.up()
  await expect(talk).toHaveAttribute('aria-pressed', 'false')
  return (await heard).postDataJSON() as Clip
}

export const RECORD_PAGE = /\/records\/[0-9a-f-]{36}$/

const RECORD_API = /\/api\/custom\/records\/[^/?]+$/

export const recordRequest = (page: Page, method: 'PUT' | 'DELETE') =>
  page.waitForRequest((r) => RECORD_API.test(r.url()) && r.method() === method)

export const createRequest = (page: Page, app: string) =>
  page.waitForResponse((r) => r.url().endsWith(`/api/custom/apps/${app}/records`) && r.request().method() === 'POST')
