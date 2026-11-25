FROM python:3.12-slim AS runtime

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --system --uid 10001 --create-home app
COPY backend backend
COPY recipes/validate.py recipes/validate.py
COPY recipes/schema recipes/schema
COPY recipes/*.yaml recipes/
COPY .github/PULL_REQUEST_TEMPLATE/recipe.md .github/PULL_REQUEST_TEMPLATE/recipe.md

USER 10001
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM runtime AS checks
USER root
RUN pip install --no-cache-dir -r backend/requirements-dev.txt
COPY recipes recipes
# Windows build contexts can mark ordinary Python source files executable.
RUN find backend recipes -type f -name '*.py' -exec chmod 644 {} +
USER 10001

# Keep development dependencies out of the default production image.
FROM runtime AS production
