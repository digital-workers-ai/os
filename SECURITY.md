# Security

## Supported versions

`main` only. There are no releases yet.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: the repository's Security tab, "Report a vulnerability", or https://github.com/digital-workers-ai/os/security/advisories/new. Never a public issue.

Include the commit (`git rev-parse --short HEAD`), the steps to reproduce and the impact. A person acknowledges within a week.

## Known limits

There is no authentication on `/api` or `/mcp`. The stack is for localhost or behind your own network boundary until the OAuth item in `TODO.md` lands.

API keys live in `app/.env`, which is gitignored, or in the environment. They are never settings, and a model layer switched on without its key refuses to start.

The operator reads a restored copy of the database in the CI runner and never touches production.

The mock estate under `mock/` is fictional data.
