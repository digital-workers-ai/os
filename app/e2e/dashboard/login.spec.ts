import { expect, mockJson, snap, test, visit } from '../fixtures'

test('login', async ({ page }) => {
  await mockJson(page, '**/api/auth/me', { detail: 'sign in' }, 401)
  await visit(page, '/')
  await expect(page.getByTestId('login')).toBeVisible()
  await expect(page.getByTestId('login-google')).toHaveAttribute('href', /\/api\/auth\/login\?next=/)
  await snap(page, 'dashboard-login')
})
