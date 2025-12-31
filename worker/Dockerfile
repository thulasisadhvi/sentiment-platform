FROM python:3.9-slim

WORKDIR /app

# 1. Install dependencies
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install asyncpg

# 2. Copy Shared Backend & Worker Code
COPY backend /app/backend
COPY worker /app/worker

# 3. Set PYTHONPATH
ENV PYTHONPATH=/app

# 4. Run as a Module (This fixes the import error)
CMD ["python", "-m", "worker.worker"]