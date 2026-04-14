# Stage 1: Build frontend
FROM node:22-slim AS frontend-builder
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.11-slim
WORKDIR /app

# Install Microsoft ODBC Driver 18 for SQL Server (required by pyodbc / aioodbc)
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg2 && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        -o /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc && \
    rm -rf /var/lib/apt/lists/*

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir -r backend/requirements.txt
EXPOSE 8000
CMD ["bash", "scripts/railway_start.sh"]
