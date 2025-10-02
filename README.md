# Kit Targeting App

A full-stack web application for kit targeting functionality.

## Tech Stack

- **Backend**: FastAPI + PostgreSQL on Supabase
- **Frontend**: React + Vite deployed on Vercel
- **Database**: PostgreSQL (Supabase)
- **Deployment**: 
  - API: Supabase
  - Web: Vercel

## Local Development

### Prerequisites
- Python 3.8+
- Node.js 16+
- Supabase account

### Running Locally

1. **Start the API server**:
   ```bash
   make api-dev
   ```
   This runs the FastAPI server with hot reload on `http://localhost:8000`

2. **Start the web development server**:
   ```bash
   make web-dev
   ```
   This runs the Vite dev server on `http://localhost:5173`

### Environment Variables

Environment variables are configured in:
- **API**: `.env` file in the `/api` directory
- **Web**: `.env.local` file in the `/web` directory

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key

## Project Structure

```
├── api/                 # FastAPI backend
├── web/                 # React frontend
├── .gitignore          # Git ignore rules
├── Makefile            # Development commands
└── README.md           # This file
```