import type { Locator, Page } from '@playwright/test'
import { expect, header, mockJson, NOW, openFilter, settle, snap, test, visit } from './fixtures'

const Q = 'wayne'
const TYPO = 'acme corpp'
const NONSENSE = 'zzqx'
const EMPTY_HINT = 'type to search everything stored · ⌘K opens search from any page'
const DEFINITION_HREFS: Record<string, string> = {
  metric: '/metrics?metric=',
  rule: '/definitions/rules?rule=',
  goal: '/definitions/goals?goal=',
  source: '/config/sources?source=',
  entity_type: '/definitions/ontology?type=',
  reading: '/definitions/enrichment?reading=',
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const at = (path: string) => new RegExp(`${escape(path)}$`)

const hrefFor = (kind: string, id: string) => {
  if (kind === 'raw') return `/entities/raw?event=${encodeURIComponent(id)}`
  if (kind === 'briefing') {
    const [role, seq] = id.split('/')
    return `/ai/coaching?role=${encodeURIComponent(role)}&briefing=${encodeURIComponent(seq)}`
  }
  const prefix = DEFINITION_HREFS[kind]
  return prefix ? `${prefix}${encodeURIComponent(id)}` : `/entities/canonical?entity=${encodeURIComponent(id)}`
}

const palette = (page: Page) => page.getByTestId('search-palette')
const input = (page: Page) => page.getByTestId('search-input')
const results = (page: Page) => page.getByTestId('search-result')
const highlighted = (page: Page) => page.locator('[data-testid="search-result"][aria-selected="true"]')
const rows = (page: Page) => page.getByTestId('search-row')
const rowsOf = (page: Page, kind: string) => page.locator(`[data-testid="search-row"][data-kind="${kind}"]`)
const title = (page: Page) => page.getByTestId('search-title')
const kinds = (scope: Locator) => scope.evaluateAll((els) => els.map((el) => el.getAttribute('data-kind')))
const count = (text: string) => Number(text.replace(/\D/g, ''))

const open = async (page: Page, key = 'Meta+k') => {
  await page.keyboard.press(key)
  await expect(palette(page)).toBeVisible()
  await expect(input(page)).toBeFocused()
}

const query = async (page: Page, q: string) => {
  await input(page).fill(q)
  await expect(results(page).first()).toBeVisible()
  await expect(page.getByTestId('loading')).toHaveCount(0)
  await expect(page.getByTestId('search-all')).toHaveText(/^View all \d[\d,]* →$/)
}

const total = async (page: Page) => {
  await expect(title(page)).toHaveText(/^Results \([1-9][\d,]*\)$/)
  await expect(rows(page).first()).toBeVisible()
  return count(await title(page).innerText())
}

const expectSelected = async (row: Locator) => {
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(row).toBeInViewport()
}

const expectNoScroll = async (page: Page, path: string) => {
  await visit(page, path)
  if (path.includes('q=')) await total(page)
  const [scrollHeight, innerHeight] = await page.evaluate(() => [document.documentElement.scrollHeight, window.innerHeight])
  expect(scrollHeight, path).toBeLessThanOrEqual(innerHeight)
}

test.describe('intro', () => {
  test.use({ contextOptions: { reducedMotion: 'no-preference' } })

  test('⌘K is inert until the page is revealed', async ({ page }) => {
    await page.clock.pauseAt(NOW)
    await page.goto('/')
    await settle(page)
    await expect(page.getByTestId('intro')).toBeVisible()
    await page.keyboard.press('Meta+k')
    await expect(palette(page)).toHaveCount(0)
    await page.clock.runFor(5000)
    await expect(page.getByTestId('intro')).toHaveCount(0)
    await open(page)
  })
})

test('palette is closed until ⌘K', async ({ page }) => {
  await visit(page, '/')
  await expect(palette(page)).toHaveCount(0)
  await open(page)
  await expect(input(page)).toHaveAttribute('placeholder', 'Search everything…')
  await expect(page.getByTestId('search-recent')).toHaveCount(0)
  await expect(results(page)).toHaveCount(0)
  const goto = page.getByTestId('search-goto')
  expect(await goto.count()).toBeGreaterThanOrEqual(20)
  await expect(goto.filter({ hasText: 'Entities · Review' })).toHaveAttribute('href', '/entities/review')
  await expect(goto.filter({ hasText: 'Config · MCP' })).toHaveAttribute('href', '/config/mcp')
  await snap(page, 'palette-open')
})

test('Ctrl+K opens, Esc and the backdrop close', async ({ page }) => {
  await visit(page, '/')
  await open(page, 'Control+k')
  await page.keyboard.press('Escape')
  await expect(palette(page)).toHaveCount(0)
  await open(page)
  await page.mouse.click(8, 792)
  await expect(palette(page)).toHaveCount(0)
})

test('route change closes the palette', async ({ page }) => {
  await visit(page, '/')
  await page.getByTestId('nav-metrics').click()
  await settle(page)
  await open(page)
  await page.goBack()
  await expect(page).toHaveURL(at('/'))
  await expect(palette(page)).toHaveCount(0)
})

test('go-to link navigates and closes', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await page.getByTestId('search-goto').filter({ hasText: 'Entities · Review' }).click()
  await expect(page).toHaveURL(at('/entities/review'))
  await expect(palette(page)).toHaveCount(0)
})

test('results are grouped by kind', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await query(page, Q)
  const groups = page.getByTestId('search-group')
  expect(await groups.count()).toBeGreaterThanOrEqual(2)
  expect(await results(page).count()).toBeLessThanOrEqual(10)
  const rowKinds = await kinds(results(page))
  expect(rowKinds).toContain('company')
  expect(await kinds(groups)).toEqual([...new Set(rowKinds)])
  await expect(palette(page).locator('[role=listbox]')).toBeVisible()
  await expect(results(page).first()).toHaveAttribute('role', 'option')
  await expect(results(page).first()).toHaveAttribute('data-id', /./)
  await expect(highlighted(page)).toHaveCount(0)
  await expect(page.getByTestId('search-all')).toHaveAttribute('href', `/search?q=${Q}`)
  await snap(page, 'palette-results')
})

test('arrow down and enter open the top hit', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await query(page, Q)
  await page.keyboard.press('ArrowDown')
  const hit = highlighted(page)
  await expect(hit).toHaveCount(1)
  await expect(input(page)).toHaveAttribute('aria-activedescendant', /./)
  const id = (await hit.getAttribute('data-id'))!
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(at(`/entities/canonical?entity=${id}`))
  await expect(palette(page)).toHaveCount(0)
  await settle(page)
  await expectSelected(page.locator(`[data-testid="entities-row"][data-id="${id}"]`))
  await expect(page.getByTestId('entity-detail-title')).not.toBeEmpty()
  await open(page)
  await expect(page.getByTestId('search-recent')).toHaveText([Q])
  await page.getByTestId('search-recent').first().click()
  await expect(input(page)).toHaveValue(Q)
  await expect(results(page).first()).toBeVisible()
})

test('enter without a highlight opens the search page', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await query(page, Q)
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(at(`/search?q=${Q}`))
  await expect(palette(page)).toHaveCount(0)
})

test('view all opens the search page and remembers the query', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await query(page, Q)
  await page.getByTestId('search-all').click()
  await expect(page).toHaveURL(at(`/search?q=${Q}`))
  await expect(palette(page)).toHaveCount(0)
  await settle(page)
  await expect(page.getByTestId('search-table')).toBeVisible()
  await expect(page.getByTestId('search-box')).toHaveValue(Q)
  await open(page)
  await expect(page.getByTestId('search-recent')).toHaveText([Q])
})

test('kind prefix narrows the palette', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await query(page, `briefing:${Q}`)
  expect(new Set(await kinds(results(page)))).toEqual(new Set(['briefing']))
  await expect(page.getByTestId('search-group')).toHaveCount(1)
  await page.getByTestId('search-all').click()
  await expect(page).toHaveURL(/\/search\?q=/)
  await settle(page)
  await total(page)
  expect(new Set(await kinds(rows(page)))).toEqual(new Set(['briefing']))
})

test('no matches', async ({ page }) => {
  await visit(page, '/')
  await open(page)
  await input(page).fill(NONSENSE)
  await expect(page.getByTestId('search-status')).toHaveText('no matches')
  await expect(page.getByTestId('loading')).toHaveCount(0)
  await expect(results(page)).toHaveCount(0)
  await snap(page, 'palette-empty')
})

test('search page empty', async ({ page }) => {
  await visit(page, '/search')
  await expect(page.getByTestId('nav-search')).toHaveAttribute('aria-current', 'page')
  await expect(page.getByTestId('page-heading')).toHaveText('Search')
  await expect(title(page)).toHaveText('Results (0)')
  await expect(page.getByTestId('search').getByTestId('empty')).toHaveText(EMPTY_HINT)
  const box = page.getByTestId('search-box')
  await expect(box).toBeFocused()
  await expect(box).toHaveAttribute('placeholder', 'Search everything…')
  await expect(page.getByTestId('search-kind-filter')).toHaveText('all kinds (0)')
  await expect(page.getByTestId('search-table')).toHaveCount(0)
  await snap(page, 'search-empty')
})

test('search page results', async ({ page }) => {
  await visit(page, `/search?q=${Q}`)
  const n = await total(page)
  expect(n).toBeGreaterThan(0)
  const table = page.getByTestId('search-table')
  for (const name of ['Kind', 'Name', 'Evidence']) await expect(header(table, name)).toBeVisible()
  await expect(rows(page)).toHaveCount(Math.min(n, 50))
  const first = rows(page).first()
  await expect(first.locator('td').first()).toHaveText((await first.getAttribute('data-kind'))!)
  const company = rowsOf(page, 'company').filter({ hasText: 'Wayne Enterprises' })
  await expect(company).toHaveCount(1)
  await expect(company.locator('td').nth(2)).toContainText(/wayne/i)
  await expect(rowsOf(page, 'briefing').first().locator('mark').first()).toHaveText(/wayne/i)
  await expect(page.locator('[data-testid^="search-mode-"]')).toHaveCount(0)
  await expect(page.getByTestId('search-kind-filter')).toHaveText(`all kinds (${n})`)
  await snap(page, 'search-results')
})

test('kind filter narrows the rows', async ({ page }) => {
  await visit(page, `/search?q=${Q}`)
  const n = await total(page)
  await openFilter(page, 'search-kind-filter')
  const option = (value: string) => page.locator(`[data-testid="search-kind-filter-option"][data-value="${value}"]`)
  await expect(option('*')).toHaveText(`all kinds (${n})`)
  await expect(option('company')).toHaveText(/^company \(\d+\)$/)
  await expect(option('briefing')).toHaveText(/^briefing \(\d+\)$/)
  const companies = count(await option('company').innerText())
  await snap(page, 'search-kind-open')
  await option('company').click()
  await expect(page).toHaveURL(/kind=company/)
  await expect(title(page)).toHaveText(`Results (${companies})`)
  await expect(rows(page)).toHaveCount(companies)
  expect(new Set(await kinds(rows(page)))).toEqual(new Set(['company']))
  await expect(page.getByTestId('search-kind-filter')).toHaveText(`company (${companies})`)
})

test('briefing prefix lists only briefings and opens the journal row', async ({ page }) => {
  await visit(page, `/search?q=briefing:${Q}`)
  await expect(title(page)).toHaveText('Results (4)')
  await expect(rows(page)).toHaveCount(4)
  expect(new Set(await kinds(rows(page)))).toEqual(new Set(['briefing']))
  const row = rows(page).first()
  const id = (await row.getAttribute('data-id'))!
  await row.click()
  await expect(page).toHaveURL(at(hrefFor('briefing', id)))
  await settle(page)
  const [role, seq] = id.split('/')
  await expect(page.getByTestId(`coaching-role-${role}`)).toHaveAttribute('aria-pressed', 'true')
  await expectSelected(page.locator(`[data-testid="coaching-row"][data-seq="${seq}"]`))
})

test('typo falls back to similar names', async ({ page }) => {
  await visit(page, `/search?q=${encodeURIComponent(TYPO)}`)
  expect(await total(page)).toBeGreaterThan(0)
  await expect(rows(page).first()).toContainText('Acme Corp')
})

test('typing drives the url', async ({ page }) => {
  await visit(page, '/search')
  await page.getByTestId('search-box').fill('globex')
  await expect(page).toHaveURL(at('/search?q=globex'))
  await expect(rows(page).first()).toContainText(/globex/i)
})

test('no results', async ({ page }) => {
  await visit(page, `/search?q=${NONSENSE}`)
  await expect(title(page)).toHaveText('Results (0)')
  await expect(page.getByTestId('search').getByTestId('empty')).toHaveText('no matches')
  await expect(page.getByTestId('search-table')).toHaveCount(0)
})

test('layer off and errors', async ({ page }) => {
  await mockJson(page, '**/api/search?*', { detail: 'EMBEDDINGS_ENABLED is off' }, 409)
  await visit(page, `/search?q=${Q}&mode=meaning`)
  await expect(page.getByTestId('search').getByTestId('banner')).toHaveText('EMBEDDINGS_ENABLED is off')
  await mockJson(page, '**/api/search?*', { detail: 'boom' }, 500)
  await visit(page, `/search?q=${Q}`)
  await expect(page.getByTestId('search').getByTestId('error-banner')).toHaveText('500 boom')
})

test('rows open the thing they name', async ({ page }) => {
  await visit(page, `/search?q=${Q}`)
  const company = rowsOf(page, 'company').first()
  const id = (await company.getAttribute('data-id'))!
  await expect(company).toHaveCSS('cursor', 'pointer')
  await company.click()
  await expect(page).toHaveURL(at(hrefFor('company', id)))
  await settle(page)
  await expectSelected(page.locator(`[data-testid="entities-row"][data-id="${id}"]`))

  await visit(page, '/search?q=mrr')
  const metric = page.locator('[data-testid="search-row"][data-kind="metric"][data-id="mrr"]')
  await expect(metric).toContainText('MRR')
  await metric.click()
  await expect(page).toHaveURL(at(hrefFor('metric', 'mrr')))
  await settle(page)
  await expectSelected(page.locator('[data-testid="metrics-row"][data-name="mrr"]'))
})

test('search page never scrolls', async ({ page }) => {
  for (const path of ['/search', `/search?q=${Q}`]) await expectNoScroll(page, path)
})

test('deep link selects a metric', async ({ page }) => {
  await visit(page, '/metrics?metric=mrr')
  await expectSelected(page.locator('[data-testid="metrics-row"][data-name="mrr"]'))
  await expect(page.getByTestId('series-title')).toHaveText('MRR')
})

test('deep link selects a briefing', async ({ page }) => {
  const history = await (await page.request.get('/api/coaching/head_of_sales/history')).json()
  const seq = Math.min(...history.briefings.map((b: { seq: number }) => b.seq))
  expect(seq).toBeGreaterThan(0)
  await visit(page, `/ai/coaching?role=head_of_sales&briefing=${seq}`)
  await expect(page.getByTestId('tab-coaching')).toHaveAttribute('data-state', 'active')
  await expect(page.getByTestId('coaching-role-head_of_sales')).toHaveAttribute('aria-pressed', 'true')
  const row = page.locator(`[data-testid="coaching-row"][data-seq="${seq}"]`)
  await expect(row).toHaveAttribute('data-state', 'selected')
  await expectSelected(row)
})

test('deep link marks a rule', async ({ page }) => {
  await visit(page, '/definitions/rules?rule=subscription_past_due')
  await expect(page.getByTestId('tab-rules')).toHaveAttribute('data-state', 'active')
  const row = page.getByTestId('definitions-rules-table').locator('tr[data-name="subscription_past_due"]')
  await expect(row).toContainText('Subscription Past Due')
  await expect(row).toHaveAttribute('data-state', 'selected')
  await expectSelected(row)
})

test('deep link marks a source', async ({ page }) => {
  await visit(page, '/config/sources?source=zendesk')
  await expect(page.getByTestId('tab-sources')).toHaveAttribute('data-state', 'active')
  const row = page.locator('[data-testid="sources-row"][data-source="zendesk"]')
  await expect(row).toHaveAttribute('data-state', 'selected')
  await expect(row).toBeInViewport()
})

test('deep link picks a raw event', async ({ page }) => {
  const { events } = await (await page.request.get('/api/raw?source=zendesk&object_type=organizations&limit=50')).json()
  const event = events.find((e: { raw_payload: { name?: string } }) => e.raw_payload.name === 'Wayne Enterprises')
  expect(event).toBeDefined()
  await visit(page, `/entities/raw?event=${event.id}`)
  await expect(page.getByTestId('tab-raw')).toHaveAttribute('data-state', 'active')
  await expect(page.getByTestId('records-source-filter')).toHaveText('zendesk')
  await expectSelected(page.locator(`[data-testid="records-row"][data-key="zendesk|organizations|${event.source_id}"]`))
  await expect(page.getByTestId('record-detail-title')).toHaveText(String(event.source_id))
  await expect(page.getByTestId('record-events').locator(`tr[data-id="${event.id}"]`)).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('record-payload')).toContainText('Wayne Enterprises')
})

test('nav lists search last', async ({ page }) => {
  await visit(page, '/search')
  const items = page.getByTestId('top-nav').locator('[data-testid^="nav-"]')
  await expect(items.last()).toHaveAttribute('data-testid', 'nav-search')
  await expect(items.last()).toHaveText('Search')
  await expect(items.last()).toHaveAttribute('aria-current', 'page')
  await expect(items.last()).toHaveClass(/bg-white/)
})
