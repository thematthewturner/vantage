# Single image for both the web terminal and the nightly scheduler.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies first (cached unless the lock/manifest changes). The
# package builds from src, so it must be present at sync time.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra app --extra prices

# Runtime assets: config (settings/sources/universe), migrations, theme.
COPY config ./config
COPY migrations ./migrations
COPY .streamlit ./.streamlit

EXPOSE 8501

# Default command runs the terminal; the scheduler service overrides it.
CMD ["streamlit", "run", "src/vantage/app/dashboard.py"]
