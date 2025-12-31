FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install asyncpg for DB and websockets for Real-time
RUN pip install asyncpg websockets

# Copy code INTO a 'backend' subdirectory
COPY . /app/backend

# Set Python Path to /app so it can find the 'backend' package
ENV PYTHONPATH=/app

# Run uvicorn pointing to the module path 'backend.main:app'
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]