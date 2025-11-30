# Connection Status

## ✅ GitHub - CONNECTED
- **Repository**: https://github.com/jeanpaul09/OracleX
- **Status**: ✅ Active and synced
- **Branch**: main
- **Remote**: origin (configured)

### Verify:
```bash
git remote -v
git status
```

---

## ✅ Vercel - CONNECTED (Perfect for Frontend!)
- **Project**: oraclex
- **Project ID**: prj_TedTdlsB2tlI1noUZ6LhG5FS8HrX
- **Dashboard**: https://vercel.com/jean-pauls-projects-7ca33fb2/oraclex
- **Status**: ✅ Linked and configured for Next.js frontend

### Configuration:
- **Root Directory**: `ui` (Next.js app)
- **Framework**: Next.js (auto-detected)
- **Build Command**: `npm run build`
- **Output Directory**: `.next`

### ✅ Perfect Setup:
Vercel is **ideal** for your Next.js frontend! The configuration is ready:
- `vercel.json` is configured for the `ui/` directory
- Frontend uses `NEXT_PUBLIC_API_URL` to connect to Railway backend
- CORS is configured on the backend to allow all Vercel domains

### Next Steps:
1. In Vercel dashboard → Settings → Environment Variables
2. Add: `NEXT_PUBLIC_API_URL=https://your-railway-url.railway.app`
3. Deploy (or push to trigger auto-deploy)

### Commands:
```bash
npx vercel  # Deploy to preview
npx vercel --prod  # Deploy to production
```

---

## ⚠️ Railway - NEEDS MANUAL CONNECTION (Backend API)
- **Status**: Not yet linked locally
- **Config**: `railway.json` is configured for FastAPI backend
- **Start Command**: `uvicorn api_server_polymarket:app --host 0.0.0.0 --port $PORT`

### Connect Railway (Choose one method):

#### Method 1: Via Railway Dashboard (Easiest - Recommended)
1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `jeanpaul09/OracleX`
5. Railway will automatically:
   - Detect Python from `requirements.txt`
   - Use `railway.json` configuration
   - Run the FastAPI server

#### Method 2: Via Railway CLI (Interactive)
```bash
# This will open a browser for authentication
npx @railway/cli login

# Then link to existing project or create new one
npx @railway/cli link
# OR
npx @railway/cli init
```

### Configuration:
- **Start Command**: `uvicorn api_server_polymarket:app --host 0.0.0.0 --port $PORT`
- **Build Command**: `pip install -r requirements.txt && playwright install chromium`
- **Build**: Automatic via Nixpacks (detects Python)
- **Restart Policy**: ON_FAILURE with 10 retries

### Environment Variables Needed:
Add these in Railway dashboard (Project → Variables):

```bash
# Polymarket API
POLYMARKET_API_KEY=your_key
POLYMARKET_PRIVATE_KEY=your_private_key

# Database
DATABASE_URL=your_database_url
REDIS_URL=your_redis_url

# LLM
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022

# Frontend URL (for CORS - set after Vercel deployment)
FRONTEND_URL=https://your-vercel-app.vercel.app

# Trading Configuration
DEMO_MODE=true
INITIAL_CAPITAL=10000.0
MAX_POSITION_SIZE=0.2
```

---

## Architecture Overview

```
┌─────────────────┐         ┌─────────────────┐
│   Vercel        │         │   Railway       │
│   (Frontend)    │────────▶│   (Backend API) │
│   Next.js UI    │  HTTP   │   FastAPI       │
│   ui/           │  WebSocket│   api_server_  │
└─────────────────┘         └─────────────────┘
```

### How They Connect:
1. **Frontend (Vercel)**: Next.js app in `ui/` directory
   - Uses `NEXT_PUBLIC_API_URL` environment variable
   - Connects to Railway backend via HTTP and WebSocket
   - Deployed automatically on every push

2. **Backend (Railway)**: FastAPI server (`api_server_polymarket.py`)
   - Serves REST API endpoints
   - Provides WebSocket for real-time updates
   - CORS configured to allow all Vercel domains

---

## Current Status Summary

| Service | Status | Purpose | Notes |
|---------|--------|---------|-------|
| **GitHub** | ✅ Connected | Source Control | Code synced, ready to push |
| **Vercel** | ✅ Linked | Frontend (Next.js) | Perfect for UI, auto-deploys |
| **Railway** | ⚠️ Needs Setup | Backend (FastAPI) | Perfect for long-running API |

---

## Recommended Deployment Order

1. **Deploy Backend First (Railway)**
   - Connect Railway via dashboard
   - Add environment variables
   - Get Railway URL (e.g., `https://oraclex-production.railway.app`)

2. **Configure Frontend (Vercel)**
   - Add `NEXT_PUBLIC_API_URL` environment variable in Vercel
   - Set value to your Railway backend URL
   - Push to trigger deployment (or deploy manually)

3. **Update Backend CORS (Railway)**
   - Add `FRONTEND_URL` environment variable in Railway
   - Set value to your Vercel frontend URL
   - Backend will automatically allow the frontend domain

---

## Quick Commands

```bash
# Check GitHub connection
git remote -v
git push origin main

# Check Vercel connection
cat .vercel/project.json
npx vercel --prod

# Connect Railway (after manual login)
npx @railway/cli link
```

---

## Documentation

- **Full Deployment Guide**: See `DEPLOYMENT.md`
- **Quick Start**: See `QUICKSTART.md`

---

## Environment Variables Reference

### Vercel (Frontend)
```bash
NEXT_PUBLIC_API_URL=https://your-railway-url.railway.app
```

### Railway (Backend)
```bash
# API Keys
POLYMARKET_API_KEY=...
ANTHROPIC_API_KEY=...

# Database
DATABASE_URL=...
REDIS_URL=...

# Frontend (for CORS)
FRONTEND_URL=https://your-vercel-app.vercel.app

# Configuration
DEMO_MODE=true
LLM_PROVIDER=anthropic
```
