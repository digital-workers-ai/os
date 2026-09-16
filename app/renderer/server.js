import http from 'node:http'
import { chromium } from 'playwright'

const PORT = 8200
const MIN_SIZE = 256
const MAX_SIZE = 4096

const browser = await chromium.launch()

const json = (res, status, body) => {
  res.writeHead(status, { 'content-type': 'application/json' })
  res.end(JSON.stringify(body))
}

const readBody = (req) =>
  new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
    req.on('error', reject)
  })

const validSize = (value) => Number.isInteger(value) && value >= MIN_SIZE && value <= MAX_SIZE

async function shot(req, res) {
  let body
  try {
    body = JSON.parse(await readBody(req))
  } catch {
    return json(res, 422, { error: 'body must be JSON' })
  }
  const { html, width, height } = body ?? {}
  if (typeof html !== 'string' || !validSize(width) || !validSize(height)) {
    return json(res, 422, { error: `html, width and height are required; sizes ${MIN_SIZE}..${MAX_SIZE}` })
  }
  const page = await browser.newPage({ viewport: { width, height } })
  try {
    await page.setContent(html, { waitUntil: 'networkidle' })
    await page.evaluate(() => document.fonts.ready)
    const png = await page.screenshot({ type: 'png' })
    res.writeHead(200, { 'content-type': 'image/png', 'content-length': png.length })
    res.end(png)
  } finally {
    await page.close()
  }
}

http
  .createServer(async (req, res) => {
    try {
      if (req.method === 'GET' && req.url === '/health') return json(res, 200, { status: 'ok' })
      if (req.method === 'POST' && req.url === '/shot') return await shot(req, res)
      json(res, 404, { error: 'not found' })
    } catch (e) {
      json(res, 500, { error: e.message })
    }
  })
  .listen(PORT)
