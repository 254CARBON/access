FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy mock service code
COPY mocks/clickhouse/ ./mocks/clickhouse/
COPY shared/ ./shared/

# Expose port
EXPOSE 8123

# Run the mock service
CMD ["python", "-m", "uvicorn", "mocks.clickhouse.server:create_app", "--host", "0.0.0.0", "--port", "8123"]
