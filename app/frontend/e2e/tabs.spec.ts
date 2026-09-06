import type { Page } from '@playwright/test'
import { expect, mockJson, settle, test, visit } from './fixtures'

const MCP = {
  path: '/mcp',
  tools: [{ name: 'get_metrics', description: 'Metric series with current value and trend' }],
  resources: [{ uri: 'definitions://ontology', name: 'ontology', description: 'Committed ontology definitions' }],
  prompts: [{ name: 'briefing_ceo', description: 'CEO briefing from the current estate' }],
}

const PAGES: { path: string; title: string; tabs: Record<string, string> }[] = [
  { path: '/entities', title: 'Entities', tabs: { canonical: 'Canonical', raw: 'Raw entities', visualize: 'Visualize' } },
  { path: '/ai', title: 'AI', tabs: { enrichment: 'Enrichment', coaching: 'Coaching' } },
  {
    path: '/definitions',
    title: 'Definitions',
    tabs: {
      ontology: 'Ontology',
      mappings: 'Mappings',
      transforms: 'Transforms',
      metrics: 'Metrics',
      rules: 'Rules',
      goals: 'Goals',
      enrichment: 'Enrichment',
    },
  },
  { path: '/config', title: 'Config', tabs: { sources: 'Sources', rebuild: 'Rebuild', mcp: 'MCP' } },
]

const DEEP: [string, string][] = [
  ['/definitions/rules', 'rules'],
  ['/ai/coaching', 'coaching'],
  ['/entities/visualize', 'visualize'],
  ['/config/mcp', 'mcp'],
]

const at = (path: string) => new RegExp(`${path}$`)
const trigger = (page: Page, tab: string) => page.getByTestId(`tab-${tab}`)
const activeTriggers = (page: Page) => page.locator('[data-testid^="tab-"][data-state="active"]')

const expectTab = async (page: Page, path: string, tab: string) => {
  await expect(page).toHaveURL(at(`${path}/${tab}`))
  await expect(trigger(page, tab)).toHaveAttribute('data-state', 'active')
  await expect(activeTriggers(page)).toHaveCount(1)
  await expect(page.getByTestId(`tabpanel-${tab}`)).toHaveAttribute('data-state', 'active')
}

for (const { path, title, tabs } of PAGES) {
  const [first, ...rest] = Object.keys(tabs)

  test(`${path} lands on ${first}`, async ({ page }) => {
    await visit(page, path)
    await expectTab(page, path, first)
    await expect(page.getByTestId(`nav-${path.slice(1)}`)).toHaveAttribute('aria-current', 'page')
  })

  test(`${path} tabs drive the url and title`, async ({ page }) => {
    await mockJson(page, '**/api/mcp', MCP)
    await visit(page, path)
    for (const tab of [...rest, first]) {
      await trigger(page, tab).click()
      await settle(page)
      await expectTab(page, path, tab)
      await expect(page).toHaveTitle(`${tabs[tab]} · ${title}`)
    }
  })
}

for (const [path, tab] of DEEP) {
  test(`deep link ${path}`, async ({ page }) => {
    await mockJson(page, '**/api/mcp', MCP)
    await visit(page, path)
    const [, section] = path.split('/')
    await expectTab(page, `/${section}`, tab)
    await expect(page.getByTestId(`nav-${section}`)).toHaveAttribute('aria-current', 'page')
  })
}

test('unknown tab falls back to the first', async ({ page }) => {
  await visit(page, '/entities/nope')
  await expectTab(page, '/entities', 'canonical')
})

test('history walks back and forward through tabs', async ({ page }) => {
  await mockJson(page, '**/api/mcp', MCP)
  await visit(page, '/config')
  await trigger(page, 'rebuild').click()
  await expectTab(page, '/config', 'rebuild')
  await trigger(page, 'mcp').click()
  await expectTab(page, '/config', 'mcp')
  await page.goBack()
  await settle(page)
  await expectTab(page, '/config', 'rebuild')
  await page.goForward()
  await settle(page)
  await expectTab(page, '/config', 'mcp')
})
