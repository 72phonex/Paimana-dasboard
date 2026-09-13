# ── Stage 1: Build the React/Vite frontend ──────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY vite.config.js index.html ./
COPY frontend/ ./frontend/

RUN npm run build
# Output lands in /app/dist

# ── Stage 2: Python runtime + serve everything from FastAPI ──────────────────
FROM python:3.11-slim

# System dependencies for PDF parsing (pdfminer / pypdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cache friendly)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy entire project
COPY . .

# Copy built frontend into the dist folder that FastAPI will serve statically
COPY --from=frontend-build /app/dist ./dist

# Render injects PORT; FastAPI listens on 0.0.0.0:$PORT
ENV PORT=8000

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
