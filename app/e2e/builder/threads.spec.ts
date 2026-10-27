import { expect, mockJson, snap, test, visit } from '../fixtures'
import { ISSUE, ready, type ThreadRow } from './ready'

const ROWS: ThreadRow[] = [
  { id: '0b6a8f4e-2c1d-4e7b-9a3f-5d8c7b6a5e41', app: null, title: 'Concrete pours', created_at: '2026-09-04T11:00:00+00:00', issue: ISSUE },
  { id: '7e2d1c0b-9f8e-4d6c-8b5a-4a3f2e1d0c92', app: 'receipts', title: 'Receipts', created_at: '2026-09-03T16:00:00+00:00', issue: null },
  { id: 'c4b3a291-8e7f-4a6b-9c5d-3e2f1a0b9c83', app: null, title: null, created_at: '2026-09-02T09:30:00+00:00', issue: null },
]

test('the conversations list shows each thread, newest first, with its issue link', async ({ page }) => {
  await mockJson(page, '**/api/builder/threads', ROWS)
  await visit(page, '/threads')
  await ready(page)
  const rows = page.getByTestId('thread-row')
  await expect(rows).toHaveCount(ROWS.length)
  for (const [n, { id }] of ROWS.entries()) await expect(rows.nth(n).getByTestId('thread-open')).toHaveAttribute('href', `/threads/${id}`)
  for (const text of ['New app', 'Concrete pours', 'Sep 4']) await expect(rows.nth(0)).toContainText(text)
  const issue = rows.nth(0).getByTestId('thread-issue')
  await expect(issue).toHaveAttribute('href', ISSUE.url)
  await expect(issue).toContainText(`#${ISSUE.number}`)
  for (const text of ['Change Receipts', 'Receipts', 'Sep 3']) await expect(rows.nth(1)).toContainText(text)
  await expect(rows.nth(1).getByTestId('thread-issue')).toHaveCount(0)
  for (const text of ['New app', 'No draft yet', 'Sep 2']) await expect(rows.nth(2)).toContainText(text)
  await expect(rows.nth(2).getByTestId('thread-issue')).toHaveCount(0)
  await snap(page, 'builder-threads')
})

test('no conversations yet shows the empty state', async ({ page }) => {
  const response = await page.request.get('/api/builder/threads')
  await expect(response).toBeOK()
  expect(await response.json()).toEqual([])
  await visit(page, '/threads')
  await ready(page)
  await expect(page.getByTestId('thread-row')).toHaveCount(0)
  await expect(page.getByTestId('threads-empty')).toContainText('No conversations yet')
  await snap(page, 'builder-threads-empty')
})
