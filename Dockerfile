FROM python:3.12-slim

RUN useradd --create-home app \
    && mkdir /data \
    && chown app /data

WORKDIR /app

# Install dependencies against a stub package first: this layer is rebuilt
# only when pyproject.toml changes, not on every source edit.
COPY pyproject.toml README.md ./
RUN mkdir -p src/caching_service \
    && touch src/caching_service/__init__.py \
    && pip install --no-cache-dir .

COPY src ./src
RUN pip install --no-cache-dir --no-deps .

USER app

ENV DATABASE_URL=sqlite:////data/cache.db
EXPOSE 8000

CMD ["uvicorn", "caching_service.api:app", "--host", "0.0.0.0", "--port", "8000"]
