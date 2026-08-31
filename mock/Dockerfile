FROM python:3.12-slim

WORKDIR /app/seeds

RUN pip install --no-cache-dir fastapi uvicorn

COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "seeds.server:app", "--host", "0.0.0.0", "--port", "8100"]
