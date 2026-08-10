# --- Stage 1: Build frontend ---
FROM node:20-slim AS frontend-build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.js tsconfig.json tsconfig.node.json ./
COPY client/ ./client/
COPY types/ ./types/
RUN npm run build

# --- Stage 2: Python backend ---
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

# Copy built frontend assets
COPY --from=frontend-build /app/dist ./dist

# Create data directory
RUN mkdir -p server/data

EXPOSE 3000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "3000"]
