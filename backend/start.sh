#!/bin/bash
# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data/FR data/Procurement data/Establishment
mkdir -p vector_store

# Run ingestion (if there are PDFs)
# python ingest.py

# Start the application
uvicorn app:app --host 0.0.0.0 --port $PORT