# Use Python 3.11 official image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy backend requirements first (for better caching)
COPY backend/requirements.txt /app/backend/
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r backend/requirements.txt

# Copy the rest of the application
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose the port
EXPOSE 8000

# Run the application
CMD cd /app/backend && uvicorn app:app --host 0.0.0.0 --port $PORT
