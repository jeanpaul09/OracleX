# Deployment Guide

## Architecture

- **Frontend (Vercel)**: Next.js UI in `ui/` directory
- **Backend (Railway)**: FastAPI server (`api_server_polymarket.py`)

## Vercel Frontend Setup

### 1. Connect Repository to Vercel

1. Go to https://vercel.com/dashboard
2. Click "Add New Project"
3. Import your GitHub repository: `jeanpaul09/OracleX`
4. Vercel will auto-detect Next.js from the `ui/` directory

### 2. Configure Vercel Project Settings

**Root Directory**: Set to `ui`

**Build Settings**:
- Framework Preset: Next.js
- Build Command: `npm run build` (or leave default)
- Output Directory: `.next` (or leave default)
- Install Command: `npm install` (or leave default)

**Environment Variables**:
```
NEXT_PUBLIC_API_URL=https://your-railway-app.railway.app
```

Replace `your-railway-app.railway.app` with your Railway backend URL.

### 3. Deploy

Vercel will automatically deploy on every push to `main` branch.

---

## Railway Backend Setup

### 1. Connect Repository to Railway

1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `jeanpaul09/OracleX`

### 2. Configure Environment Variables

In Railway dashboard → Your Project → Variables, add:

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

# Frontend URL (for CORS)
FRONTEND_URL=https://your-vercel-app.vercel.app

# Trading Configuration
DEMO_MODE=true
INITIAL_CAPITAL=10000.0
MAX_POSITION_SIZE=0.2
```

### 3. Railway Configuration

Railway will automatically:
- Detect Python from `requirements.txt`
- Use `railway.json` configuration
- Run: `uvicorn api_server_polymarket:app --host 0.0.0.0 --port $PORT`

### 4. Get Railway URL

After deployment, Railway will provide a URL like:
`https://your-app-name.railway.app`

**Copy this URL** and add it to Vercel environment variables as `NEXT_PUBLIC_API_URL`.

---

## Connecting Frontend to Backend

### Step 1: Deploy Backend First

1. Deploy to Railway
2. Get the Railway URL (e.g., `https://oraclex-production.railway.app`)
3. Test the API: `https://your-railway-url.railway.app/api/polymarket/status`

### Step 2: Configure Frontend

1. In Vercel dashboard → Your Project → Settings → Environment Variables
2. Add:
   ```
   NEXT_PUBLIC_API_URL=https://your-railway-url.railway.app
   ```
3. Redeploy the frontend (or push a new commit)

### Step 3: Update Backend CORS

The backend (`api_server_polymarket.py`) is already configured to allow:
- All `*.vercel.app` domains
- Your custom Vercel domain (if set via `FRONTEND_URL`)

If you have a custom domain on Vercel, add it to Railway environment variables:
```
FRONTEND_URL=https://your-custom-domain.com
```

---

## Testing the Connection

### 1. Test Backend API

```bash
curl https://your-railway-url.railway.app/api/polymarket/status
```

Should return JSON with system status.

### 2. Test Frontend

1. Visit your Vercel URL
2. Open browser DevTools → Network tab
3. Check if API calls to Railway backend are successful
4. Check WebSocket connection (should connect to `wss://your-railway-url.railway.app/ws/polymarket`)

### 3. Common Issues

**CORS Errors**:
- Make sure `FRONTEND_URL` in Railway matches your Vercel domain
- Check that the API server allows your Vercel domain in CORS

**WebSocket Connection Failed**:
- Ensure Railway URL uses `https://` (not `http://`)
- WebSocket will automatically use `wss://` protocol

**API 404 Errors**:
- Verify `NEXT_PUBLIC_API_URL` is set correctly in Vercel
- Check that Railway backend is running and accessible

---

## Local Development

### Frontend (Vercel-like)
```bash
cd ui
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Backend (Railway-like)
```bash
pip install -r requirements.txt
playwright install chromium
uvicorn api_server_polymarket:app --host 0.0.0.0 --port 8000 --reload
```

---

## Production Checklist

- [ ] Backend deployed to Railway
- [ ] Backend URL accessible and API endpoints working
- [ ] Environment variables set in Railway
- [ ] Frontend deployed to Vercel
- [ ] `NEXT_PUBLIC_API_URL` set in Vercel to Railway URL
- [ ] CORS configured correctly (backend allows Vercel domain)
- [ ] WebSocket connection working
- [ ] Custom domains configured (if applicable)
- [ ] SSL certificates valid (automatic on both platforms)

---

## URLs Reference

After deployment, you'll have:

- **Frontend**: `https://your-app.vercel.app`
- **Backend API**: `https://your-app.railway.app`
- **API Docs**: `https://your-app.railway.app/docs`
- **WebSocket**: `wss://your-app.railway.app/ws/polymarket`
