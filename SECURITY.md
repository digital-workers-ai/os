# Security

## Supported versions

`main` only. There are no releases yet.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: the repository's Security tab, "Report a vulnerability", or https://github.com/digital-workers-ai/os/security/advisories/new. Never a public issue.

Include the commit (`git rev-parse --short HEAD`), the steps to reproduce and the impact. A person acknowledges within a week.

## Known limits

With `AUTH_ENABLED` unset there is no authentication on `/api` or `/mcp`. Postgres, the backend and the mock providers bind to the loopback interface, so `/mcp` is reachable from the machine the stack runs on only; the four web apps bind as before and proxy `/api`, so keep the stack behind your own network boundary. With `AUTH_ENABLED` set, `/mcp` requires Google sign-in from an account in `AUTH_ALLOWED_EMAILS`, `/api` requires the session cookie or a bearer, either an MCP token the server issued or an API key, and the four web apps show a sign-in card, so the stack may face a network you do not control provided `PUBLIC_URL` is HTTPS. API keys are stored as sha256 hashes and shown once; the session cookie is httponly and signed with `AUTH_JWT_SIGNING_KEY`, and rotating that key signs everyone out and invalidates every MCP token.

Provider keys live in `app/.env`, which is gitignored, or in the environment. They are never settings, and a model layer switched on without its key refuses to start.

The operator reads a restored copy of the database in the CI runner and never touches production.

The mock providers under `mock/` serve fictional data.
