# Kit Targeting API

FastAPI backend for the Kit Targeting application.

## Local Development

### Prerequisites
- Python 3.8+
- PostgreSQL database (Supabase)

### Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   Create a `.env` file in the `/api` directory with:
   ```env
   DATABASE_URL=postgresql://username:password@host:port/database
   CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://kittargetingapp.vercel.app
   APP_ENV=dev
   TZ=America/New_York
   ```

3. **Run the development server**:
   ```bash
   uvicorn app.main:app --reload
   ```
   
   Or use the Makefile:
   ```bash
   make api-dev
   ```

The API will be available at `http://localhost:8000`

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (Supabase)
- `CORS_ORIGINS`: Comma-separated list of allowed origins
- `APP_ENV`: Environment (dev|prod)
- `TZ`: Timezone (default: America/New_York)

### Supabase Setup

Before running migrations, you need to enable the required PostgreSQL extensions in your Supabase database:

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

These extensions are required for:
- `citext`: Case-insensitive text for email addresses
- `btree_gist`: GiST exclusion constraints for preventing overlapping date ranges

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Health Check

- `GET /healthz` - Returns API health status
# Trigger API deployment
