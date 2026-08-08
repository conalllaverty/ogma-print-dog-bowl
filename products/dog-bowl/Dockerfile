FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY generator ./generator
COPY data ./data
COPY assets ./assets

# Prefer Liberation for bold when Arial isn't present in the image
RUN mkdir -p /app/assets/fonts \
 && cp /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf /app/assets/fonts/Arial-Bold.ttf 2>/dev/null || true \
 && cp /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf /app/assets/fonts/Arial-Rounded-Bold.ttf 2>/dev/null || true

ENV APP_ENV=production
ENV JOBS_ROOT=/data/jobs
EXPOSE 8080
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
