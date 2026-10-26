FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ENV PYTHONUNBUFFERED=1 MOCK_BASE_URL=http://localhost:8100
RUN groupadd --gid 10001 preview && useradd --uid 10001 --gid preview --create-home preview

WORKDIR /app
COPY app/backend/pyproject.toml ./
COPY mock/requirements.txt /adversarial/seeds/
RUN pip install --no-cache-dir supervisor==4.3.0 . -r /adversarial/seeds/requirements.txt
COPY app/backend/ ./
COPY definitions/ ./definitions/
COPY .claude/skills/ ./.claude/skills/
COPY mock/ /adversarial/seeds/
COPY app/preview/supervisord.conf /etc/supervisord.conf
COPY app/preview/env.sh app/preview/serve.sh app/preview/seed.sh /preview/

USER 10001:10001
CMD ["/preview/serve.sh"]
