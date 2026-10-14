# Interdec Platform: one container serving the API and the web app.
# Stage 1 builds the Nuxt SPA to static files; stage 2 runs FastAPI, which serves both.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npx nuxt generate

FROM python:3.12-slim
# WeasyPrint (quotation PDFs) needs Pango, plus fonts for the PDF Design font choices
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
RUN rm -f backend/interdec.db backend/.secret_key
COPY --from=web /web/.output/public ./web
ENV INTERDEC_STATIC_DIR=/app/web
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
