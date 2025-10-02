# API Deployment Guide

## Quick Deploy to Render (Recommended)

1. **Create a new Web Service on Render:**
   - Go to https://render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the `api` folder as the root directory

2. **Configure the service:**
   - **Build Command:** `pip install -r requirements.txt && alembic upgrade head`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Python Version:** 3.11

3. **Set Environment Variables:**
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `CORS_ORIGINS`: `http://localhost:3000,http://localhost:5173,https://web-i2xumnks2-nates-projects-b0f17eca.vercel.app`
   - `APP_ENV`: `production`
   - `TZ`: `America/New_York`

4. **Deploy:**
   - Click "Create Web Service"
   - Wait for deployment to complete
   - Copy the service URL (e.g., `https://your-app-name.onrender.com`)

## Alternative: Railway

1. **Connect to Railway:**
   - Go to https://railway.app
   - Connect your GitHub repository
   - Select the `api` folder

2. **Configure:**
   - Railway will auto-detect Python
   - Set the same environment variables as above
   - Deploy

## Update Frontend

After deploying your API, update the Vercel environment variable:

1. **In Vercel Dashboard:**
   - Go to your project settings
   - Go to "Environment Variables"
   - Add/Update: `VITE_API_URL` = `https://your-api-url.onrender.com`

2. **Redeploy:**
   - Trigger a new deployment in Vercel

## Local Development

To run the API locally:

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
