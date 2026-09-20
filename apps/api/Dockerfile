FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/requirements-production.lock ./requirements-production.lock
RUN pip install --no-cache-dir -r requirements-production.lock
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/src ./src
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 appuser
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
COPY apps/api/scripts/smoke.py ./scripts/smoke.py
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m chase201.catalog --approve-real-catalog && exec uvicorn chase201.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
