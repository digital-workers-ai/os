import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, settle, snap, test, visit } from './fixtures'

test.describe.configure({ mode: 'default' })

const ME = '**/api/auth/me'
const KEYS = '**/api/auth/keys'
const CLIENTS = '**/api/auth/clients'
const CALLS = '**/api/mcp/calls'

const OPEN = { auth: 'open', email: null }
const GOOGLE = { auth: 'google', email: 'ana@example.com' }
const DENIED = { detail: 'sign in required' }

const KEY_ROWS = [
  { seq: 1, prefix: 'os_a1b2c3d4', label: 'ci', created_by: 'ana@example.com', created_at: '2026-09-01T10:00:00Z', last_used_at: '2026-09-03T09:00:00Z' },
  { seq: 2, prefix: 'os_e5f6a7b8', label: 'laptop', created_by: 'bo@example.com', created_at: '2026-09-02T10:00:00Z', last_used_at: null },
]
const CLIENT_ROWS = [
  {
    seq: 1,
    client_name: 'Claude',
    redirect_uri: 'https://claude.ai/api/mcp/auth_callback',
    email: 'ana@example.com',
    created_at: '2026-09-01T12:00:00Z',
    last_seen_at: '2026-09-03T08:00:00Z',
  },
  {
    seq: 2,
    client_name: 'Claude Code',
    redirect_uri: 'http://localhost:53311/callback',
    email: 'bo@example.com',
    created_at: '2026-09-02T12:00:00Z',
    last_seen_at: null,
  },
]
const CALL_ROWS = [
  { subject: 'ana@example.com', name: 'get_metrics', calls: 12, failed: 1, last_at: '2026-09-03T09:30:00Z' },
  { subject: null, name: 'find_entities', calls: 3, failed: 0, last_at: '2026-09-02T09:30:00Z' },
]
const CREATED = { seq: 3, prefix: 'os_c9d0e1f2', label: 'script', key: 'os_c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4' }

const heads = (table: Locator) => table.locator('th')

const openAccess = async (page: Page) => {
  await visit(page, '/config')
  await page.getByTestId('tab-access').click()
  await settle(page)
}

const mockLists = async (page: Page) => {
  await mockJson(page, KEYS, KEY_ROWS)
  await mockJson(page, CLIENTS, CLIENT_ROWS)
  await mockJson(page, CALLS, CALL_ROWS)
}

test('login', async ({ page }) => {
  await mockJson(page, ME, DENIED, 401)
  await visit(page, '/config')
  await expect(page.getByTestId('login')).toBeVisible()
  await expect(page.getByTestId('login-google')).toHaveAttribute('href', /^\/api\/auth\/login\?next=/)
  await expect(page.getByTestId('login-denied')).toHaveCount(0)
  await expect(page.getByTestId('page-main')).toHaveCount(0)
  await snap(page, 'login')
})

test('login denied', async ({ page }) => {
  await mockJson(page, ME, DENIED, 401)
  await visit(page, '/config?login=denied')
  await expect(page.getByTestId('login-denied')).toHaveText(
    'That account is not allowed. Ask whoever runs this DW-OS to add it to AUTH_ALLOWED_EMAILS.',
  )
  await snap(page, 'login-denied')
})

test('access tab, google', async ({ page }) => {
  await mockJson(page, ME, GOOGLE)
  await mockLists(page)
  await openAccess(page)
  await expect(page.getByTestId('access-me')).toContainText('Signed in as ana@example.com')
  await expect(page.getByTestId('access-signout')).toHaveText('Sign out')
  await expect(heads(page.getByTestId('access-keys-table'))).toHaveText(['Label', 'Prefix', 'Created by', 'Created', 'Last used', ''])
  await expect(page.getByTestId('access-keys-table').locator('td').nth(1)).toHaveText('os_a1b2c3d4…')
  await expect(heads(page.getByTestId('access-clients-table'))).toHaveText(['Client', 'Person', 'Authorized', 'Last seen', ''])
  await expect(page.getByTestId('access-clients-table')).toContainText('https://claude.ai/api/mcp/auth_callback')
  await expect(heads(page.getByTestId('access-callers-table'))).toHaveText(['Person', 'Tool', 'Calls', 'Failed', 'Last call'])
  await expect(page.getByTestId('access-callers-table').locator('tbody tr').nth(1).locator('td').first()).toHaveText('open')
  await snap(page, 'config-access')
  const revoke = page.getByTestId('access-keys-revoke').first()
  await expect(revoke).toHaveText('Revoke')
  await revoke.click()
  await expect(revoke).toHaveText('Confirm')
  await expect(page.getByTestId('access-keys-revoke').nth(1)).toHaveText('Revoke')
})

test('access tab, open', async ({ page }) => {
  await mockJson(page, ME, OPEN)
  await mockJson(page, CALLS, CALL_ROWS)
  await openAccess(page)
  await expect(page.getByTestId('access-me')).toContainText(
    'Access is open. Set AUTH_ENABLED to require Google sign-in; API keys and connected clients appear then.',
  )
  await expect(page.getByTestId('access-keys')).toHaveCount(0)
  await expect(page.getByTestId('access-clients')).toHaveCount(0)
  await expect(page.getByTestId('access-callers')).toBeVisible()
  await expect(heads(page.getByTestId('access-callers-table'))).toHaveText(['Person', 'Tool', 'Calls', 'Failed', 'Last call'])
  await snap(page, 'config-access-open')
})

test('new key', async ({ page }) => {
  await mockJson(page, ME, GOOGLE)
  await mockLists(page)
  await page.route(KEYS, (r) =>
    r.request().method() === 'POST'
      ? r.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(CREATED) })
      : r.fulfill({ json: KEY_ROWS }),
  )
  await openAccess(page)
  await expect(page.getByTestId('access-keys-created')).toHaveCount(0)
  await page.getByTestId('access-keys-new').click()
  const create = page.getByTestId('access-keys-create')
  await expect(create).toBeDisabled()
  await page.getByTestId('access-keys-label').fill('script')
  await expect(create).toBeEnabled()
  await create.click()
  const created = page.getByTestId('access-keys-created')
  await expect(created).toContainText('Copy it now; it is shown once.')
  await expect(created).toContainText(CREATED.key)
  await expect(page.getByTestId('access-keys-label')).toHaveCount(0)
  await snap(page, 'config-access-created')
})

test('an expired session returns to the sign-in card', async ({ page }) => {
  await mockJson(page, ME, GOOGLE)
  await mockLists(page)
  await openAccess(page)
  await mockJson(page, KEYS, DENIED, 401)
  await page.getByTestId('access-keys-new').click()
  await page.getByTestId('access-keys-label').fill('script')
  await page.getByTestId('access-keys-create').click()
  await expect(page.getByTestId('login')).toBeVisible()
})
