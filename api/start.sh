#!/bin/bash
set -e

echo "Starting Kit Targeting API..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the FastAPI server
echo "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port $PORT
