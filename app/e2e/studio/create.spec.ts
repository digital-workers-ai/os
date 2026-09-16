import { expect, mockJson, NOW, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface ThreadRow {
  seq: number
  title: string
}

const THREAD = { seq: 9001, title: 'New thread', created_at: NOW.toISOString() }

const THREADS_ROUTE = { threads: [THREAD], thread: THREAD }

const ASKED = {
  id: 1,
  role: 'person',
  text: 'Make a carousel from the pillars',
  skill_run: null,
  asset_seq: null,
  created_at: NOW.toISOString(),
}

const ANSWERED = {
  id: 2,
  role: 'studio',
  text: 'Nothing is being made: Studio is off in this stack.',
  skill_run: null,
  asset_seq: null,
  created_at: NOW.toISOString(),
}

const THREAD_ROUTE = { seq: THREAD.seq, title: THREAD.title, turns: [], turn: ASKED, reply: ANSWERED, skill_run: null, asset: null }

test('the seeded thread', async ({ page }) => {
  const { threads } = (await (await page.request.get('/api/studio/threads')).json()) as { threads: ThreadRow[] }
  expect(threads).toHaveLength(1)
  await visit(page, '/create')
  await ready(page)
  await expect(page.getByTestId('create-intro')).toBeVisible()
  await expect(page.getByTestId('thread-row')).toHaveCount(1)
  await expect(page.getByTestId('thread-row')).toContainText('a post on the coverage gate')

  await page.getByTestId('thread-row').click()
  await ready(page)
  await expect(page.getByTestId('turn')).toHaveCount(2)
  await expect(page.locator('[data-testid="turn"][data-role="person"]')).toContainText('Make a post about the coverage gate')
  await expect(page.locator('[data-testid="turn"][data-role="studio"]')).toContainText('Writing one post on the test gate')
  await expect(page.getByTestId('run-card')).toHaveAttribute('data-status', 'ok')
  await expect(page.getByTestId('run-progress')).toContainText('dw-post')
  await expect(page.getByTestId('run-asset')).toContainText('A spreadsheet has no test gate')
  await expect(page.getByTestId('run-claims')).toHaveText('3/3 claims verified')

  await ready(page)
  await snap(page, 'studio-create')
})

test('a new thread takes a turn', async ({ page }) => {
  await mockJson(page, '**/api/studio/threads', THREADS_ROUTE)
  await mockJson(page, `**/api/studio/threads/${THREAD.seq}`, THREAD_ROUTE)
  await visit(page, '/create')
  await ready(page)

  const opened = page.waitForRequest((r) => r.url().endsWith('/api/studio/threads') && r.method() === 'POST')
  await page.getByTestId('thread-new').click()
  await opened
  await expect(page).toHaveURL(new RegExp(`/create/${THREAD.seq}$`))
  await ready(page)
  await expect(page.getByTestId('thread')).toContainText(THREAD.title)
  await expect(page.getByTestId('turns-empty')).toBeVisible()

  const sent = page.waitForRequest((r) => r.url().endsWith(`/api/studio/threads/${THREAD.seq}`) && r.method() === 'POST')
  await page.getByTestId('composer-input').fill(ASKED.text)
  await page.getByTestId('composer-send').click()
  await sent
  await expect(page.getByTestId('composer-input')).toHaveValue('')
  await expect(page.getByTestId('error-banner')).toHaveCount(0)

  await ready(page)
  await snap(page, 'studio-create-new')
})
