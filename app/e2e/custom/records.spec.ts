import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { NOT_COUNTED, ready, recordRequest } from './ready'
import { listed, seededRecord } from './seeded'

const SEEDED = ['Harbor Fuel', 'Northside Office Supply']

const rows = (page: Page) => page.getByTestId('record-row')

async function savedLot(page: Page, lot: string): Promise<string> {
  const created = await page.request.post('/api/custom/apps/batch_trace/records', { data: { files: [], scan: lot, audio: null } })
  expect(created.status()).toBe(201)
  const { id } = (await created.json()) as { id: string }
  const saved = await page.request.put(`/api/custom/records/${id}`, { data: { fields: { lot, step: 'packed', quantity: 40, unit: 'cases' } } })
  await expect(saved).toBeOK()
  return id
}

test('the receipts list shows the seeded receipts in listing order and opens one', async ({ page }) => {
  const newestFirst = (await listed(page, 'receipts')).map((record) => String(record.fields.vendor)).filter((vendor) => SEEDED.includes(vendor))
  expect([...newestFirst].sort()).toEqual([...SEEDED].sort())
  const fuel = await seededRecord(page, 'receipts', 'vendor', 'Harbor Fuel')

  await visit(page, '/apps/receipts')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receipts')
  for (const vendor of SEEDED) await expect(rows(page).filter({ hasText: vendor })).toHaveCount(1)
  const shown = (await rows(page).allInnerTexts()).flatMap((text) => SEEDED.filter((vendor) => text.includes(vendor)))
  expect(shown).toEqual(newestFirst)

  await rows(page).filter({ hasText: 'Harbor Fuel' }).click()
  await expect(page).toHaveURL(new RegExp(`/records/${fuel}$`))
})

test('a seeded receipt shows its fields and its audit history', async ({ page }) => {
  const id = await seededRecord(page, 'receipts', 'vendor', 'Harbor Fuel')
  await visit(page, `/records/${id}`)
  await ready(page)
  await expect(page.getByTestId('field-vendor')).toHaveValue('Harbor Fuel')
  await expect(page.getByTestId('field-date')).toHaveValue('2026-09-03')
  await expect(page.getByTestId('field-total')).toHaveValue(/^48\.20?$/)
  await expect(page.getByTestId('field-category')).toHaveValue('fuel')
  await expect(page.getByTestId('field-items-0-description')).toHaveValue('Diesel')
  await expect(page.getByTestId('field-items-0-amount')).toHaveValue(/^48\.20?$/)
  const history = page.getByTestId('record-history')
  await expect(history).toContainText(/save/i)
  await expect(history).toContainText(/view/i)
  await expect(history).toContainText('admin')
  await ready(page)
  await snap(page, 'custom-record', { mask: [history] })
})

test('a fresh save counts in the numbers only after the next rebuild', async ({ page }) => {
  const id = await savedLot(page, 'LOT-3101')
  await visit(page, `/records/${id}`)
  await ready(page)
  await expect(page.getByTestId('field-lot')).toHaveValue('LOT-3101')
  await expect(page.getByTestId('field-step')).toHaveValue('packed')
  await expect(page.getByTestId('record-not-counted')).toHaveText(NOT_COUNTED)
})

test('the history lists create, save, view and edit, oldest first', async ({ page }) => {
  const id = await savedLot(page, 'LOT-3102')
  await visit(page, `/records/${id}`)
  await ready(page)
  const history = page.getByTestId('record-history')
  await expect(history).toContainText(/view/i)
  const before = (await history.innerText()).toLowerCase()
  expect(before.indexOf('create')).toBeGreaterThanOrEqual(0)
  expect(before.indexOf('save')).toBeGreaterThan(before.indexOf('create'))
  expect(before.indexOf('view')).toBeGreaterThan(before.indexOf('save'))
  expect(before).toContain('admin')
  expect(before).not.toContain('edit')

  await page.getByTestId('field-note').fill('Pallet 3 re-wrapped')
  const edited = recordRequest(page, 'PUT')
  await page.getByTestId('save').click()
  expect((await edited).postDataJSON().fields).toMatchObject({ lot: 'LOT-3102', note: 'Pallet 3 re-wrapped' })
  await expect(history).toContainText(/edit/i)
  const after = (await history.innerText()).toLowerCase()
  expect(after.lastIndexOf('edit')).toBeGreaterThan(after.indexOf('view'))

  await visit(page, `/records/${id}`)
  await ready(page)
  await expect(page.getByTestId('field-note')).toHaveValue('Pallet 3 re-wrapped')
})

test('remove asks in the app, then the record leaves the list', async ({ page }) => {
  const id = await savedLot(page, 'LOT-5582')
  const dialogs: string[] = []
  page.on('dialog', (dialog) => {
    dialogs.push(dialog.type())
    void dialog.dismiss()
  })
  const deletes: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'DELETE') deletes.push(request.url())
  })
  await visit(page, '/apps/batch_trace')
  await ready(page)
  const row = rows(page).filter({ hasText: 'LOT-5582' })
  await expect(row).toHaveCount(1)
  await row.click()
  await expect(page).toHaveURL(new RegExp(`/records/${id}$`))
  await ready(page)

  const confirm = page.getByRole('alertdialog').or(page.getByRole('dialog'))
  await page.getByTestId('remove').click()
  await expect(confirm).toBeVisible()
  await expect(confirm.getByTestId('remove-confirm')).toBeVisible()
  await ready(page)
  await snap(page, 'custom-record-remove', { mask: [page.getByTestId('record-history')] })
  await confirm.getByRole('button', { name: 'Cancel' }).click()
  await expect(confirm).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`/records/${id}$`))
  expect(deletes).toEqual([])

  await page.getByTestId('remove').click()
  const removed = recordRequest(page, 'DELETE')
  await page.getByTestId('remove-confirm').click()
  expect((await removed).url()).toMatch(new RegExp(`/api/custom/records/${id}$`))
  await expect(page).toHaveURL(/\/apps\/batch_trace$/)
  await ready(page)
  await expect(rows(page).filter({ hasText: 'LOT-5582' })).toHaveCount(0)
  expect(dialogs).toEqual([])
})
