FROM node:20-bookworm-slim AS node

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright MOCK_BASE_URL=http://localhost:8100 RENDER_URL=http://localhost:8200
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
RUN pip install --no-cache-dir supervisor

WORKDIR /render
COPY app/renderer/package.json ./
RUN npm install --omit=dev && npx playwright install --with-deps chromium
COPY app/renderer/server.js ./

WORKDIR /app
COPY app/backend/pyproject.toml ./
COPY mock/requirements.txt /adversarial/seeds/
RUN pip install --no-cache-dir . -r /adversarial/seeds/requirements.txt
COPY app/backend/ ./
COPY definitions/ ./definitions/
COPY .claude/skills/ ./.claude/skills/
COPY mock/ /adversarial/seeds/
COPY app/preview/supervisord.conf /etc/supervisord.conf
COPY app/preview/env.sh app/preview/serve.sh app/preview/seed.sh /preview/

CMD ["/preview/serve.sh"]
