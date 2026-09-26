FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
# gcc and python3-dev are often needed for compiling some ML packages if wheels aren't available
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the API
# Render expects web services to listen on port 10000 by default (or the PORT env var)
# We will use the PORT environment variable
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-10000}
