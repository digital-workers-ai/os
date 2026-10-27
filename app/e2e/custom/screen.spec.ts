import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { createRequest, PHOTO, RECORD_PAGE, ready, recordRequest } from './ready'
import { seededRecord } from './seeded'

interface Detail {
  files: { path: string; media_type: string; kind: string }[]
}

const STROKE: [number, number][] = [
  [0.15, 0.6],
  [0.3, 0.3],
  [0.45, 0.7],
  [0.6, 0.35],
  [0.75, 0.65],
  [0.85, 0.4],
]

const signature = (page: Page) => page.getByTestId('field-signature').getByRole('img', { name: 'Signature' })

async function sign(page: Page) {
  const pad = page.getByTestId('signature-pad')
  await pad.scrollIntoViewIfNeeded()
  const box = (await pad.boundingBox())!
  const [[x, y], ...rest] = STROKE
  await page.mouse.move(box.x + box.width * x, box.y + box.height * y)
  await page.mouse.down()
  for (const [dx, dy] of rest) await page.mouse.move(box.x + box.width * dx, box.y + box.height * dy, { steps: 8 })
  await page.mouse.up()
}

async function signatureFile(page: Page, id: string) {
  const image = signature(page)
  await expect(image).toHaveAttribute('src', new RegExp(`/api/custom/records/${id}/files/`))
  const file = await page.request.get((await image.getAttribute('src'))!)
  expect(file.status()).toBe(200)
  expect(file.headers()['content-type']).toMatch(/^image\/png/)
  const detail = (await (await page.request.get(`/api/custom/records/${id}`)).json()) as Detail
  expect(detail.files).toContainEqual(expect.objectContaining({ kind: 'signature', media_type: 'image/png' }))
}

test('a drawn signature is saved as the record signature file', async ({ page }) => {
  await visit(page, '/apps/proof_of_delivery/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Proof of delivery')
  const created = createRequest(page, 'proof_of_delivery')
  await page.locator('input[type="file"]').setInputFiles(PHOTO)
  expect((await created).status()).toBe(201)
  await page.getByTestId('field-order_number').fill('2077')
  await page.getByTestId('field-signed_by').fill('Sam Lee')
  await page.getByTestId('field-condition').selectOption('good')

  const done = page.getByTestId('signature-done')
  await expect(page.getByTestId('signature-pad')).toBeVisible()
  await expect(done).toBeDisabled()
  await sign(page)
  await expect(done).toBeEnabled()
  await page.getByTestId('signature-clear').click()
  await expect(done).toBeDisabled()
  await sign(page)
  await done.click()
  await expect(signature(page)).toBeVisible()
  await ready(page)
  await snap(page, 'custom-signature-new')

  const saved = recordRequest(page, 'PUT')
  await page.getByTestId('save').click()
  expect((await saved).postDataJSON().fields).toMatchObject({ order_number: '2077', signed_by: 'Sam Lee', condition: 'good' })
  await expect(page).toHaveURL(RECORD_PAGE)
  await ready(page)
  await expect(signature(page)).toBeVisible()
  await signatureFile(page, page.url().split('/').pop()!)
})

test('the seeded delivery shows its signature', async ({ page }) => {
  const id = await seededRecord(page, 'proof_of_delivery', 'order_number', '1042')
  await visit(page, `/records/${id}`)
  await ready(page)
  await expect(page.getByTestId('field-signed_by')).toHaveValue('Jordan Rivera')
  await expect(page.getByTestId('field-condition')).toHaveValue('good')
  await expect(signature(page)).toBeVisible()
  await signatureFile(page, id)
  await ready(page)
  await snap(page, 'custom-signature-seeded', { mask: [page.getByTestId('record-history')] })
})
