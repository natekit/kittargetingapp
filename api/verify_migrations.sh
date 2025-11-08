#!/bin/bash
# Verification script for migrations
# Run this in Render shell to verify migrations work before deploying

set -e

echo "=== Migration Verification Script ==="
echo ""

# Check current heads
echo "1. Checking current migration heads..."
alembic heads
echo ""

# Check current database revision
echo "2. Checking current database revision..."
alembic current
echo ""

# Show migration history
echo "3. Showing migration history (last 10)..."
alembic history | head -10
echo ""

# Try to upgrade (dry run - won't actually run)
echo "4. Checking what migrations would be applied..."
alembic upgrade head --sql
echo ""

# Check if users table exists
echo "5. Checking if users table exists..."
python3 << EOF
from app.db import engine
from sqlalchemy import inspect, text

inspector = inspect(engine)
tables = inspector.get_table_names()

if 'users' in tables:
    print("✅ users table EXISTS")
    # Check columns
    columns = [col['name'] for col in inspector.get_columns('users')]
    print(f"   Columns: {', '.join(columns)}")
else:
    print("❌ users table DOES NOT EXIST")
    print(f"   Existing tables: {', '.join(tables)}")

if 'plans' in tables:
    print("✅ plans table EXISTS")
else:
    print("❌ plans table DOES NOT EXIST")
EOF

echo ""
echo "=== Verification Complete ==="

