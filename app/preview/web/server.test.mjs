import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { once } from 'node:events'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import http from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer, idTokens, start } from './server.mjs'

const apiUrl = 'https://os-pr-12-api-6011343381.us-central1.run.app'
const metadataUrl =
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity' +
  '?audience=https%3A%2F%2Fos-pr-12-api-6011343381.us-central1.run.app'
const immutable = 'public, max-age=31536000, immutable'
const index = '<!doctype html><title>console</title>'
const minutes = 60_000
const types = {
  html: 'text/html; charset=utf-8',
  js: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8',
  svg: 'image/svg+xml',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  ico: 'image/x-icon',
  json: 'application/json; charset=utf-8',
  woff: 'font/woff',
  woff2: 'font/woff2',
  txt: 'text/plain; charset=utf-8',
  map: 'application/json; charset=utf-8',
  webmanifest: 'application/manifest+json',
  bin: 'application/octet-stream',
}

let root
let dist

before(async () => {
  root = await mkdtemp(join(tmpdir(), 'preview-web-'))
  dist = join(root, 'dist')
  await mkdir(join(dist, 'assets'), { recursive: true })
  await mkdir(join(dist, 'fonts'))
  await mkdir(join(dist, 'docs', 'guide'), { recursive: true })
  await mkdir(join(dist, 'types'))
  await writeFile(join(dist, 'index.html'), index)
  await writeFile(join(dist, 'assets', 'app.js'), 'console.log("app")')
  await writeFile(join(dist, 'fonts', 'x.woff2'), 'font')
  await writeFile(join(dist, 'docs', 'guide', 'intro.txt'), 'nested')
  await writeFile(join(root, 'secret'), 'secret')
  for (const extension of Object.keys(types)) {
    await writeFile(join(dist, 'types', `file.${extension}`), extension)
  }
})

after(() => rm(root, { recursive: true, force: true }))

async function collect(body) {
  const chunks = []
  for await (const chunk of body) chunks.push(Buffer.from(chunk))
  return Buffer.concat(chunks).toString()
}

function upstream(respond = () => new Response('upstream')) {
  const calls = []
  const fetch = async (url, init = {}) => {
    const call = {
      url: String(url),
      method: init.method ?? 'GET',
      headers: new Headers(init.headers),
      duplex: init.duplex,
      body: init.body == null ? null : await collect(init.body),
    }
    calls.push(call)
    return respond(call)
  }
  return { calls, fetch }
}

function close(server) {
  server.close()
  server.closeAllConnections()
}

async function send(port, path, { method = 'GET', headers = {}, body = [] } = {}) {
  const request = http.request({ host: '127.0.0.1', port, path, method, headers, agent: false })
  for (const chunk of body) request.write(chunk)
  request.end()
  const [response] = await once(request, 'response')
  return { status: response.statusCode, headers: response.headers, body: await collect(response) }
}

async function serve(t, { respond, idToken } = {}) {
  const audiences = []
  const { calls, fetch } = upstream(respond)
  const server = createServer({
    dist,
    apiUrl,
    idToken:
      idToken ??
      (async (audience) => {
        audiences.push(audience)
        return 'id-token'
      }),
    fetch,
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  t.after(() => close(server))
  const { port } = server.address()
  return { calls, audiences, port, send: (path, options) => send(port, path, options) }
}

test('createServer returns an http.Server that is not yet listening', () => {
  const server = createServer({ dist, apiUrl, idToken: async () => 'id-token', fetch: upstream().fetch })
  assert.ok(server instanceof http.Server)
  assert.equal(server.listening, false)
})

test('/ serves index.html with no-cache', async (t) => {
  const { send } = await serve(t)
  const response = await send('/')
  assert.equal(response.status, 200)
  assert.equal(response.headers['content-type'], types.html)
  assert.equal(response.headers['cache-control'], 'no-cache')
  assert.equal(response.body, index)
})

test('files under /assets/ are cached as immutable', async (t) => {
  const { send } = await serve(t)
  const response = await send('/assets/app.js')
  assert.equal(response.status, 200)
  assert.equal(response.headers['content-type'], types.js)
  assert.equal(response.headers['cache-control'], immutable)
  assert.equal(response.body, 'console.log("app")')
})

test('files outside /assets/ are served with no-cache', async (t) => {
  const { send } = await serve(t)
  const response = await send('/fonts/x.woff2')
  assert.equal(response.status, 200)
  assert.equal(response.headers['content-type'], types.woff2)
  assert.equal(response.headers['cache-control'], 'no-cache')
  assert.equal(response.body, 'font')
})

test('a nested file is served from its directory', async (t) => {
  const { send } = await serve(t)
  const response = await send('/docs/guide/intro.txt')
  assert.equal(response.status, 200)
  assert.equal(response.body, 'nested')
})

for (const [extension, type] of Object.entries(types)) {
  test(`a .${extension} file is served as ${type}`, async (t) => {
    const { send } = await serve(t)
    const response = await send(`/types/file.${extension}`)
    assert.equal(response.status, 200)
    assert.equal(response.headers['content-type'], type)
    assert.equal(response.body, extension)
  })
}

test('a query string is ignored when resolving a file', async (t) => {
  const { send } = await serve(t)
  const response = await send('/assets/app.js?v=2')
  assert.equal(response.status, 200)
  assert.equal(response.body, 'console.log("app")')
})

test('a missing path without an extension falls back to index.html with no-cache', async (t) => {
  const { send } = await serve(t)
  const response = await send('/projects/42')
  assert.equal(response.status, 200)
  assert.equal(response.headers['content-type'], types.html)
  assert.equal(response.headers['cache-control'], 'no-cache')
  assert.equal(response.body, index)
})

test('the index.html fallback stays no-cache under /assets/', async (t) => {
  const { send } = await serve(t)
  const response = await send('/assets/missing')
  assert.equal(response.status, 200)
  assert.equal(response.headers['cache-control'], 'no-cache')
  assert.equal(response.body, index)
})

test('a directory path falls back to index.html', async (t) => {
  const { send } = await serve(t)
  const response = await send('/docs/guide')
  assert.equal(response.status, 200)
  assert.equal(response.body, index)
})

test('a missing path with an extension is 404', async (t) => {
  const { send } = await serve(t)
  const response = await send('/assets/missing.js')
  assert.equal(response.status, 404)
})

test('a path that climbs out of dist is 404', async (t) => {
  const { send } = await serve(t)
  const response = await send('/../secret')
  assert.equal(response.status, 404)
  assert.ok(!response.body.includes('secret'))
})

test('an encoded path that climbs out of dist is 404', async (t) => {
  const { send } = await serve(t)
  const response = await send('/%2e%2e/secret')
  assert.equal(response.status, 404)
  assert.ok(!response.body.includes('secret'))
})

test('a malformed percent-encoding is 404', async (t) => {
  const { send } = await serve(t)
  const response = await send('/%E0%A4%A')
  assert.equal(response.status, 404)
})

test('HEAD answers with the headers and no body', async (t) => {
  const { send } = await serve(t)
  const response = await send('/assets/app.js', { method: 'HEAD' })
  assert.equal(response.status, 200)
  assert.equal(response.headers['content-type'], types.js)
  assert.equal(response.headers['cache-control'], immutable)
  assert.equal(response.body, '')
})

test('methods other than GET and HEAD are 405 outside the proxy', async (t) => {
  const { send } = await serve(t)
  const response = await send('/', { method: 'POST', body: ['x'] })
  assert.equal(response.status, 405)
})

test('paths under /api/ are proxied to apiUrl with the same method', async (t) => {
  const { calls, send } = await serve(t)
  const response = await send('/api/entities/7')
  assert.equal(response.status, 200)
  assert.equal(response.body, 'upstream')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, `${apiUrl}/api/entities/7`)
  assert.equal(calls[0].method, 'GET')
})

test('/api itself is proxied with its query', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api?limit=2&q=a%20b')
  assert.equal(calls[0].url, `${apiUrl}/api?limit=2&q=a%20b`)
})

test('/mcp itself is proxied', async (t) => {
  const { calls, send } = await serve(t)
  await send('/mcp')
  assert.equal(calls[0].url, `${apiUrl}/mcp`)
})

test('paths under /mcp/ are proxied', async (t) => {
  const { calls, send } = await serve(t)
  await send('/mcp/messages?session=9')
  assert.equal(calls[0].url, `${apiUrl}/mcp/messages?session=9`)
})

test('a path that merely starts with api or mcp is served statically', async (t) => {
  const { calls, send } = await serve(t)
  assert.equal((await send('/apiary')).body, index)
  assert.equal((await send('/mcpx')).body, index)
  assert.equal(calls.length, 0)
})

test('the proxy authenticates with an identity token for apiUrl', async (t) => {
  const { audiences, calls, send } = await serve(t)
  await send('/api/entities')
  assert.deepEqual(audiences, [apiUrl])
  assert.equal(calls[0].headers.get('x-serverless-authorization'), 'Bearer id-token')
})

test('the proxy forwards the incoming host and the http protocol', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities', { headers: { host: 'preview.test' } })
  assert.equal(calls[0].headers.get('x-forwarded-host'), 'preview.test')
  assert.equal(calls[0].headers.get('x-forwarded-proto'), 'http')
})

test('the proxy overrides client-sent serverless authorization and forwarding headers', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities', {
    headers: {
      host: 'preview.test',
      'x-serverless-authorization': 'Bearer forged',
      'x-forwarded-host': 'forged.test',
      'x-forwarded-proto': 'https',
    },
  })
  assert.equal(calls[0].headers.get('x-serverless-authorization'), 'Bearer id-token')
  assert.equal(calls[0].headers.get('x-forwarded-host'), 'preview.test')
  assert.equal(calls[0].headers.get('x-forwarded-proto'), 'http')
})

test('the proxy copies the other request headers', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities', { headers: { accept: 'application/json', cookie: 'session=abc', 'x-custom': 'kept' } })
  assert.equal(calls[0].headers.get('accept'), 'application/json')
  assert.equal(calls[0].headers.get('cookie'), 'session=abc')
  assert.equal(calls[0].headers.get('x-custom'), 'kept')
})

test('the proxy drops host, authorization and hop-by-hop request headers', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities', {
    method: 'POST',
    body: ['payload'],
    headers: {
      host: 'preview.test',
      authorization: 'Bearer user-token',
      connection: 'keep-alive',
      'keep-alive': 'timeout=5',
      'proxy-authenticate': 'Basic',
      'proxy-authorization': 'Basic dXNlcg==',
      te: 'trailers',
      trailer: 'x-checksum',
      upgrade: 'h2c',
      'x-custom': 'kept',
    },
  })
  const dropped = [
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
  ]
  for (const name of dropped) assert.equal(calls[0].headers.has(name), false, name)
  assert.equal(calls[0].headers.get('x-custom'), 'kept')
})

test('the proxy streams a request body upstream with duplex half', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities', { method: 'POST', body: ['{"name":', '"acme"}'] })
  assert.equal(calls[0].method, 'POST')
  assert.equal(calls[0].duplex, 'half')
  assert.equal(calls[0].body, '{"name":"acme"}')
})

test('the proxy sends no body for GET', async (t) => {
  const { calls, send } = await serve(t)
  await send('/api/entities')
  assert.equal(calls[0].body, null)
})

test('the proxy forwards HEAD without a body', async (t) => {
  const { calls, send } = await serve(t, {
    respond: () => new Response(null, { headers: { 'x-upstream': 'head' } }),
  })
  const response = await send('/api/entities', { method: 'HEAD' })
  assert.equal(calls[0].method, 'HEAD')
  assert.equal(calls[0].body, null)
  assert.equal(response.status, 200)
  assert.equal(response.headers['x-upstream'], 'head')
  assert.equal(response.body, '')
})

test('the proxy keeps the upstream status and headers', async (t) => {
  const { send } = await serve(t, {
    respond: () =>
      new Response('{"id":7}', { status: 201, headers: { 'content-type': 'application/json', 'x-upstream': 'yes' } }),
  })
  const response = await send('/api/entities', { method: 'POST', body: ['{}'] })
  assert.equal(response.status, 201)
  assert.equal(response.headers['content-type'], 'application/json')
  assert.equal(response.headers['x-upstream'], 'yes')
  assert.equal(response.body, '{"id":7}')
})

test('the proxy keeps every upstream set-cookie', async (t) => {
  const { send } = await serve(t, {
    respond: () =>
      new Response('ok', {
        headers: [
          ['set-cookie', 'a=1; Path=/'],
          ['set-cookie', 'b=2; Path=/'],
        ],
      }),
  })
  const response = await send('/api/login')
  assert.deepEqual(response.headers['set-cookie'], ['a=1; Path=/', 'b=2; Path=/'])
})

test('the proxy drops content-encoding, content-length and transfer-encoding from the upstream response', async (t) => {
  const { send } = await serve(t, {
    respond: () =>
      new Response('plain', {
        headers: { 'content-encoding': 'gzip', 'content-length': '5', 'transfer-encoding': 'gzip, chunked' },
      }),
  })
  const response = await send('/api/entities')
  assert.equal(response.headers['content-encoding'], undefined)
  assert.equal(response.headers['content-length'], undefined)
  assert.equal(response.headers['transfer-encoding'], 'chunked')
  assert.equal(response.body, 'plain')
})

test('the proxy streams the upstream body as it arrives', { timeout: 5000 }, async (t) => {
  const encoder = new TextEncoder()
  let release
  const released = new Promise((resolve) => {
    release = resolve
  })
  const { port } = await serve(t, {
    respond: () =>
      new Response(
        new ReadableStream({
          async start(controller) {
            controller.enqueue(encoder.encode('first'))
            await released
            controller.enqueue(encoder.encode('second'))
            controller.close()
          },
        }),
      ),
  })
  const request = http.get({ host: '127.0.0.1', port, path: '/api/stream', agent: false })
  const [response] = await once(request, 'response')
  const chunks = response[Symbol.asyncIterator]()
  assert.equal(String((await chunks.next()).value), 'first')
  release()
  assert.equal(await collect(chunks), 'second')
})

test('an upstream body that fails mid-stream aborts the response and the server keeps serving', { timeout: 5000 }, async (t) => {
  const encoder = new TextEncoder()
  let fail
  const { port, send } = await serve(t, {
    respond: (call) =>
      call.url.endsWith('/api/broken')
        ? new Response(
            new ReadableStream({
              start(controller) {
                controller.enqueue(encoder.encode('partial'))
                fail = () => controller.error(new Error('upstream broke'))
              },
            }),
          )
        : new Response('fine'),
  })
  const request = http.get({ host: '127.0.0.1', port, path: '/api/broken', agent: false })
  const [response] = await once(request, 'response')
  const chunks = response[Symbol.asyncIterator]()
  assert.equal(String((await chunks.next()).value), 'partial')
  fail()
  await assert.rejects(chunks.next())
  assert.equal((await send('/api/fine')).body, 'fine')
})

test('a failing idToken answers 502 without calling the API', async (t) => {
  const { calls, send } = await serve(t, {
    idToken: async () => {
      throw new Error('metadata server unreachable')
    },
  })
  const response = await send('/api/entities')
  assert.equal(response.status, 502)
  assert.match(response.headers['content-type'], /^text\/plain/)
  assert.equal(calls.length, 0)
})

test('a failing fetch answers 502 in plain text without the token', async (t) => {
  const { send } = await serve(t, {
    respond: () => {
      throw new Error('connect refused with Bearer id-token')
    },
  })
  const response = await send('/api/entities')
  assert.equal(response.status, 502)
  assert.match(response.headers['content-type'], /^text\/plain/)
  assert.ok(response.body.length > 0)
  assert.ok(!response.body.includes('id-token'))
})

test('idTokens asks the metadata server for an identity token for the audience', async () => {
  const { calls, fetch } = upstream(() => new Response('meta-token'))
  assert.equal(await idTokens({ fetch, now: () => 0 })(apiUrl), 'meta-token')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, metadataUrl)
  assert.equal(calls[0].method, 'GET')
  assert.equal(calls[0].headers.get('metadata-flavor'), 'Google')
})

test('idTokens trims the token', async () => {
  const { fetch } = upstream(() => new Response('  meta-token\n'))
  assert.equal(await idTokens({ fetch, now: () => 0 })(apiUrl), 'meta-token')
})

test('idTokens reuses a token for an audience within 45 minutes', async () => {
  let clock = 0
  let issued = 0
  const { calls, fetch } = upstream(() => new Response(`token-${++issued}`))
  const idToken = idTokens({ fetch, now: () => clock })
  assert.equal(await idToken(apiUrl), 'token-1')
  clock = 45 * minutes - 1
  assert.equal(await idToken(apiUrl), 'token-1')
  assert.equal(calls.length, 1)
})

test('idTokens fetches a fresh token once 45 minutes have passed', async () => {
  let clock = 0
  let issued = 0
  const { calls, fetch } = upstream(() => new Response(`token-${++issued}`))
  const idToken = idTokens({ fetch, now: () => clock })
  assert.equal(await idToken(apiUrl), 'token-1')
  clock = 45 * minutes
  assert.equal(await idToken(apiUrl), 'token-2')
  assert.equal(calls.length, 2)
})

test('idTokens caches each audience separately', async () => {
  let issued = 0
  const { calls, fetch } = upstream(() => new Response(`token-${++issued}`))
  const idToken = idTokens({ fetch, now: () => 0 })
  assert.equal(await idToken(apiUrl), 'token-1')
  assert.equal(await idToken('https://other.run.app'), 'token-2')
  assert.equal(await idToken(apiUrl), 'token-1')
  assert.deepEqual(
    calls.map((call) => call.url),
    [metadataUrl, metadataUrl.replace(/audience=.*/, 'audience=https%3A%2F%2Fother.run.app')],
  )
})

test('idTokens throws on a non-2xx metadata response', async () => {
  const { fetch } = upstream(() => new Response('denied', { status: 403 }))
  await assert.rejects(idTokens({ fetch, now: () => 0 })(apiUrl), Error)
})

test('start rejects when API_URL is missing', async () => {
  await assert.rejects(start({ PORT: '0', DIST: dist }, { fetch: upstream().fetch }), /API_URL/)
})

test('start listens on 0.0.0.0 at PORT and serves DIST', async (t) => {
  const server = await start({ PORT: '0', DIST: dist, API_URL: apiUrl }, { fetch: upstream().fetch })
  t.after(() => close(server))
  assert.equal(server.address().address, '0.0.0.0')
  assert.equal((await send(server.address().port, '/')).body, index)
})

test('start listens on 8080 when PORT is unset', async (t) => {
  const server = await start({ DIST: dist, API_URL: apiUrl }, { fetch: upstream().fetch })
  t.after(() => close(server))
  assert.equal(server.address().port, 8080)
})

test('start proxies with a metadata-server token fetched through deps.fetch', async (t) => {
  const { calls, fetch } = upstream((call) =>
    call.url.startsWith('http://metadata.google.internal/') ? new Response('meta-token\n') : new Response('from api'),
  )
  const server = await start({ PORT: '0', DIST: dist, API_URL: apiUrl }, { fetch })
  t.after(() => close(server))
  const response = await send(server.address().port, '/api/entities')
  assert.equal(response.body, 'from api')
  assert.deepEqual(
    calls.map((call) => call.url),
    [metadataUrl, `${apiUrl}/api/entities`],
  )
  assert.equal(calls[1].headers.get('x-serverless-authorization'), 'Bearer meta-token')
})

test('start falls back to globalThis.fetch when deps are omitted', async (t) => {
  const { calls, fetch } = upstream((call) =>
    call.url.startsWith('http://metadata.google.internal/') ? new Response('meta-token') : new Response('from api'),
  )
  const original = globalThis.fetch
  globalThis.fetch = fetch
  t.after(() => {
    globalThis.fetch = original
  })
  const server = await start({ PORT: '0', DIST: dist, API_URL: apiUrl })
  t.after(() => close(server))
  assert.equal((await send(server.address().port, '/api/entities')).body, 'from api')
  assert.equal(calls.length, 2)
})

test('start without DIST does not expose the files next to server.mjs', async (t) => {
  const server = await start({ PORT: '0', API_URL: apiUrl }, { fetch: upstream().fetch })
  t.after(() => close(server))
  assert.equal((await send(server.address().port, '/server.test.mjs')).status, 404)
})
