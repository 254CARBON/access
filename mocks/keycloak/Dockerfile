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
COPY mocks/keycloak/ ./mocks/keycloak/
COPY shared/ ./shared/

# Expose port
EXPOSE 8080

# Run the mock service
CMD ["python", "-m", "uvicorn", "mocks.keycloak.server:create_app", "--host", "0.0.0.0", "--port", "8080"]
