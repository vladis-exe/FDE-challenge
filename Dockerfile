# One image for the web process and the worker; docker-compose / Railway pick the command.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

# The app never writes to /app (state lives in Postgres), so root-owned files are fine.
RUN useradd --create-home app
USER app

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "gunicorn config.wsgi --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 --access-logfile -"]
