# ==========================================
# Stage 1: Build the SvelteKit Frontend
# ==========================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

# Swap SvelteKit configuration to use Node adapter and install it
COPY frontend/ .
RUN sed -i "s/@sveltejs\/adapter-auto/@sveltejs\/adapter-node/g" svelte.config.js
RUN npm install --save-dev @sveltejs/adapter-node
RUN npm run build

# ==========================================
# Stage 2: Final Run Container (Python + Node)
# ==========================================
FROM python:3.12-slim

# Install Node.js 20.x runtime, curl (for health checks), and sqlite3
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    sqlite3 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend files
COPY backend/ ./backend/

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/build ./frontend/build
COPY --from=frontend-builder /app/frontend/package.json ./frontend/
# Install production SvelteKit dependencies
RUN cd frontend && npm install --omit=dev

# Copy database & startup script
COPY start.sh .
RUN chmod +x start.sh

# Expose public SvelteKit port
EXPOSE 8080

ENV PORT=8080
ENV HOST=0.0.0.0
ENV NODE_ENV=production
ENV VITE_API_URL=""

# Fly.io expects data in a persistent volume if we want to save SQLite & uploads
# Default data folder (we'll link database.db here in fly.toml)
RUN mkdir -p /data

CMD ["./start.sh"]
