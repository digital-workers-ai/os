import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { createRequest, NOT_COUNTED, PHOTO, RECORD_PAGE, ready, recordRequest } from './ready'

interface Created {
  files: { name: string; media_type: string; data: string }[]
}

interface Saved {
  fields: Record<string, unknown> & { items: { description: string; amount: unknown }[] }
}

const TOP = ['vendor', 'date', 'total', 'tax', 'category']

async function photographed(page: Page): Promise<Created> {
  await visit(page, '/apps/receipts/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receipts')
  const input = page.locator('input[type="file"]')
  await expect(input).toHaveAttribute('capture', 'environment')
  await expect(input).toHaveAttribute('accept', /image/)
  const created = createRequest(page, 'receipts')
  await input.setInputFiles(PHOTO)
  const response = await created
  expect(response.status()).toBe(201)
  return response.request().postDataJSON() as Created
}

test('a receipt photo with AI off opens empty fields', async ({ page }) => {
  const { files } = await photographed(page)
  expect(files).toHaveLength(1)
  expect(files[0].media_type).toBe('image/jpeg')
  expect(files[0].data).toMatch(/^\/9j\//)
  await expect(page.getByTestId('retake')).toBeVisible()
  for (const name of TOP) await expect(page.getByTestId(`field-${name}`)).toHaveValue('')
  await expect(page.getByTestId('field-items-0-description')).toHaveCount(0)
  await ready(page)
  await snap(page, 'custom-receipt-empty')
})

test('typed fields and line items save, and the receipt joins the list', async ({ page }) => {
  await photographed(page)
  await page.getByTestId('field-vendor').fill('Corner Hardware')
  await page.getByTestId('field-date').fill('2026-09-04')
  await page.getByTestId('field-total').fill('23.50')
  await page.getByTestId('field-tax').fill('1.75')
  await page.getByTestId('field-category').selectOption('tools')
  const add = page.getByRole('button', { name: 'Add item' })
  await add.click()
  await page.getByTestId('field-items-0-description').fill('Hammer')
  await page.getByTestId('field-items-0-amount').fill('18.00')
  await add.click()
  await page.getByTestId('field-items-1-description').fill('Nails')
  await page.getByTestId('field-items-1-amount').fill('5.50')
  await expect(page.getByTestId('field-items-2-description')).toHaveCount(0)
  await ready(page)
  await snap(page, 'custom-receipt-typed')

  const saved = recordRequest(page, 'PUT')
  await page.getByTestId('save').click()
  const { fields } = (await saved).postDataJSON() as Saved
  expect(fields).toMatchObject({ vendor: 'Corner Hardware', date: '2026-09-04', category: 'tools' })
  expect(Number(fields.total)).toBe(23.5)
  expect(Number(fields.tax)).toBe(1.75)
  expect(fields.items.map((item) => [item.description, Number(item.amount)])).toEqual([
    ['Hammer', 18],
    ['Nails', 5.5],
  ])
  await expect(page).toHaveURL(RECORD_PAGE)
  await ready(page)
  await expect(page.getByTestId('record-not-counted')).toHaveText(NOT_COUNTED)
  await expect(page.getByTestId('field-vendor')).toHaveValue('Corner Hardware')

  await visit(page, '/apps/receipts')
  await ready(page)
  await expect(page.getByTestId('record-row').filter({ hasText: 'Corner Hardware' }).first()).toBeVisible()
})
