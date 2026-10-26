import { once } from 'node:events'
import { readFile } from 'node:fs/promises'
import http from 'node:http'
import { extname, join, resolve, sep } from 'node:path'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { fileURLToPath } from 'node:url'

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.json': 'application/json; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
}
const unforwarded = new Set([
  'host',
  'authorization',
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])
const unreturned = new Set(['content-encoding', 'content-length', 'transfer-encoding'])
const proxied = /^\/(api|mcp)(\/|\?|$)/
const bodiless = new Set(['GET', 'HEAD'])
const metadata = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity'
const tokenLifetime = 45 * 60_000

async function proxy(request, response, { apiUrl, idToken, fetch }) {
  let upstream
  try {
    const forwarded = Object.entries(request.headers).filter(([name]) => !unforwarded.has(name))
    upstream = await fetch(apiUrl + request.url, {
      method: request.method,
      headers: {
        ...Object.fromEntries(forwarded),
        'x-serverless-authorization': `Bearer ${await idToken(apiUrl)}`,
        'x-forwarded-host': request.headers.host,
        'x-forwarded-proto': 'http',
      },
      body: bodiless.has(request.method) ? undefined : request,
      duplex: 'half',
    })
  } catch {
    response.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' }).end('api unreachable')
    return
  }
  for (const [name, value] of upstream.headers) if (!unreturned.has(name)) response.appendHeader(name, value)
  response.writeHead(upstream.status)
  if (!upstream.body) return response.end()
  await pipeline(Readable.fromWeb(upstream.body), response).catch(() => response.destroy())
}

const notFound = (response) => response.writeHead(404).end()
const readable = (path) => readFile(path).catch(() => null)

async function serveFile(request, response, dist) {
  if (!bodiless.has(request.method)) return response.writeHead(405).end()
  const pathname = request.url.split('?')[0]
  let path
  try {
    path = join(dist, decodeURIComponent(pathname))
  } catch {
    return notFound(response)
  }
  if (!path.startsWith(dist + sep)) return notFound(response)
  const requested = await readable(path)
  if (!requested && extname(path)) return notFound(response)
  const file = requested ? path : join(dist, 'index.html')
  const content = requested ?? (await readable(file))
  if (!content) return notFound(response)
  response.writeHead(200, {
    'content-type': types[extname(file)] ?? 'application/octet-stream',
    'cache-control': requested && pathname.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache',
  })
  response.end(content)
}

export function createServer({ dist, apiUrl, idToken, fetch }) {
  const root = resolve(dist)
  return http.createServer((request, response) =>
    proxied.test(request.url)
      ? proxy(request, response, { apiUrl, idToken, fetch })
      : serveFile(request, response, root),
  )
}

export function idTokens({ fetch, now }) {
  const cache = new Map()
  return async (audience) => {
    const cached = cache.get(audience)
    if (cached && now() - cached.at < tokenLifetime) return cached.token
    const response = await fetch(`${metadata}?audience=${encodeURIComponent(audience)}`, {
      headers: { 'Metadata-Flavor': 'Google' },
    })
    if (!response.ok) throw new Error(`metadata server answered ${response.status}`)
    const token = (await response.text()).trim()
    cache.set(audience, { token, at: now() })
    return token
  }
}

export async function start(env, { fetch = globalThis.fetch } = {}) {
  if (!env.API_URL) throw new Error('API_URL is required')
  const server = createServer({
    dist: env.DIST ?? fileURLToPath(new URL('dist', import.meta.url)),
    apiUrl: env.API_URL,
    idToken: idTokens({ fetch, now: Date.now }),
    fetch,
  })
  server.listen(Number(env.PORT ?? 8080), '0.0.0.0')
  await once(server, 'listening')
  return server
}
