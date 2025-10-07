#!/bin/bash
# Render build script for API only
echo "Building Kit Targeting API..."

# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

echo "Build complete!"
