# Kit Targeting App

A full-stack web application for kit targeting functionality.

## Tech Stack

- **Backend**: FastAPI + PostgreSQL
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Database**: PostgreSQL
- **Deployment**: 
  - API: Render (or your preferred hosting)
  - Web: Vercel

## Local Development

### Prerequisites
- Python 3.8+
- Node.js 16+
- PostgreSQL database

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
- **API**: `.env` file in the `/api` directory (copy from `.env.example`)
- **Web**: `.env` file in the `/web` directory (copy from `.env.example`)

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `CORS_ORIGINS`: Comma-separated list of allowed origins
- `VITE_API_URL`: API URL for the frontend

## Vercel Deployment

### Prerequisites
- GitHub repository with your code
- Vercel account
- API deployed on Render (or your preferred hosting)

### Deployment Steps

1. **Connect Vercel to your GitHub repository**:
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "New Project"
   - Import your GitHub repository
   - **Important**: Set the **Project Root Directory** to `web`

2. **Configure Environment Variables**:
   - In Vercel project settings, go to "Environment Variables"
   - Add the following variable:
     - `VITE_API_URL`: Your Render API URL (e.g., `https://your-api.onrender.com`)

3. **Deploy**:
   - Vercel will automatically deploy your React app
   - Your app will be available at `https://your-app.vercel.app`

### API Deployment (Render)

1. **Deploy your FastAPI backend to Render**:
   - Connect your GitHub repository to Render
   - Set the root directory to `api`
   - Add environment variables:
     - `DATABASE_URL`: Your PostgreSQL connection string
     - `CORS_ORIGINS`: Your Vercel app URL + local development URLs
     - `APP_ENV`: `production`
     - `TZ`: `America/New_York`

2. **Update CORS settings**:
   - Ensure your API allows requests from your Vercel domain
   - The API is configured to use `CORS_ORIGINS` environment variable

## 🚀 Quick Start Checklist

### Database Setup (Supabase/PostgreSQL)
- [ ] **1. Run database extensions**:
  ```sql
  CREATE EXTENSION IF NOT EXISTS citext;
  CREATE EXTENSION IF NOT EXISTS btree_gist;
  ```

### Local Development
- [ ] **2. API setup**:
  ```bash
  cd api && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload
  ```
  - API runs on `http://localhost:8000`
  - Database migrations applied automatically

- [ ] **3. Web setup**:
  ```bash
  cd web && npm i && npm run dev
  ```
  - Web app runs on `http://localhost:5173`

### Data Setup & Workflow
- [ ] **4. Seed creators**: Upload `CPC Creators.csv` to `/api/seed/creators`
  - Creates 600+ creators from CSV
  - Maps by `owner_email` and `acct_id`

- [ ] **5. Create entities**: Use Admin page to create:
  - **Advertiser** → **Campaign** → **Insertion** (with CPC)
  - Cascading dropdowns for easy selection

- [ ] **6. Upload Performance CSV** (Mon/Wed/Fri):
  - Upload to `/api/uploads/performance`
  - Matches creators via `owner_email` in Creator field
  - Shows unmatched creators for review

- [ ] **7. Upload Conversions CSV** (weekly):
  - Upload to `/api/uploads/conversions` with date range
  - **Override behavior**: Replaces overlapping date ranges
  - Tracks replaced vs inserted rows

- [ ] **8. Analytics & Planning**:
  - Check **Leaderboard** for performance metrics
  - Run **Planner** with budget and target CPA
  - Export results as CSV for analysis

### Production Deployment
- [ ] **9. Deploy to production**:
  - **API**: Deploy to Render (root directory: `api`)
  - **Web**: Deploy to Vercel (root directory: `web`)
  - Set environment variables in both platforms

## Project Structure

```
├── api/                 # FastAPI backend
│   ├── app/            # Application code
│   ├── alembic/        # Database migrations
│   ├── tests/          # Pytest test suite
│   ├── .env.example    # Environment variables template
│   └── requirements.txt
├── web/                # React frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   ├── .env.example    # Environment variables template
│   └── vercel.json     # Vercel configuration (optional)
├── .gitignore          # Git ignore rules
├── Makefile            # Development commands
└── README.md           # This file
```# Trigger Vercel redeploy
# Force deployment trigger
# Force web project deployment Thu Oct  2 11:12:06 EDT 2025
# Test commit with correct user
# Trigger deployment
