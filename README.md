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

## Project Structure

```
├── api/                 # FastAPI backend
│   ├── app/            # Application code
│   ├── alembic/        # Database migrations
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
```