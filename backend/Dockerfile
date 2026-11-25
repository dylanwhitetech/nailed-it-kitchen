FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --system --uid 10001 --create-home app
COPY backend backend
COPY recipes/validate.py recipes/validate.py
COPY recipes/schema recipes/schema
COPY recipes/*.yaml recipes/

USER 10001
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
