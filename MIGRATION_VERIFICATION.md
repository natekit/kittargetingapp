# Migration Verification Guide

## Problem
The `users` table doesn't exist because Alembic had multiple heads and couldn't run `alembic upgrade head`.

## Solution
Created a merge migration (`merge_all_heads_final`) that combines all heads into a single head.

## Verification Steps (Run in Render Shell)

### Option 1: Quick Check (Recommended)
```bash
cd /opt/render/project/src/api
python3 -m alembic heads
```
**Expected output:** Should show only `merge_all_heads_final (head)`

### Option 2: Check Current Database State
```bash
cd /opt/render/project/src/api
python3 -m alembic current
```
**Expected output:** Shows current database revision (might be empty if migrations never ran)

### Option 3: Check if Tables Exist
```bash
cd /opt/render/project/src/api
python3 << EOF
from app.db import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()

print("Existing tables:", ', '.join(tables))
print("users table exists:", 'users' in tables)
print("plans table exists:", 'plans' in tables)
EOF
```

### Option 4: Run Full Verification Script
```bash
cd /opt/render/project/src/api
bash verify_migrations.sh
```

### Option 5: Test Migration (Dry Run)
```bash
cd /opt/render/project/src/api
python3 -m alembic upgrade head --sql
```
**Expected output:** Shows SQL that would be executed (should include CREATE TABLE for users and plans)

### Option 6: Actually Run Migration (If Verification Passes)
```bash
cd /opt/render/project/src/api
python3 -m alembic upgrade head
```
**Expected output:** Should show migrations being applied, including creation of users and plans tables

## What to Look For

✅ **Good Signs:**
- Single head: `merge_all_heads_final (head)`
- Migration runs without errors
- `users` and `plans` tables exist after migration

❌ **Bad Signs:**
- Multiple heads shown
- Migration errors about missing revisions
- Tables still don't exist after migration

## If Verification Fails

1. Check the migration history:
   ```bash
   python3 -m alembic history
   ```

2. Check what revisions are in the database:
   ```bash
   python3 -m alembic current
   ```

3. If needed, you can manually stamp the database to a specific revision:
   ```bash
   python3 -m alembic stamp merge_all_heads_final
   ```

## After Verification Passes

Once you've verified:
1. The migration works in Render shell
2. Tables are created successfully
3. You can test signup and it works

Then we can push to main and let Render auto-deploy.

