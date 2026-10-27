# Production image: build the React client, then serve it and the FastAPI API together.
FROM node:24-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/tests/fixtures ./tests/fixtures
RUN pip install --no-cache-dir .
COPY --from=frontend-build /frontend/dist ./static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
