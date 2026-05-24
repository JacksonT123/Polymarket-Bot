FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN uv run alembic upgrade head || true

EXPOSE 8000

CMD ["uv", "run", "polymarket-bot", "start"]
