# Connection Status

## ✅ GitHub - CONNECTED
- **Repository**: https://github.com/jeanpaul09/OracleX
- **Status**: Active
- **Branch**: main
- **Remote**: origin

### Commands:
```bash
git remote -v  # View remotes
git push origin main  # Push to GitHub
```

---

## ✅ Vercel - CONNECTED
- **Project**: oraclex
- **Dashboard**: https://vercel.com/jean-pauls-projects-7ca33fb2/oraclex
- **Status**: Linked (deployment size issue - see notes below)

### Current Issue:
The project exceeds Vercel's 250MB serverless function limit due to large dependencies (playwright, etc.). 

### Solutions:
1. **Use Railway instead** (recommended for Python apps with heavy dependencies)
2. **Optimize dependencies** - remove unused packages
3. **Use Vercel for API only** - deploy a lighter version without browser automation

### Commands:
```bash
npx vercel  # Deploy to preview
npx vercel --prod  # Deploy to production
```

---

## ⚠️ Railway - NEEDS MANUAL SETUP
Railway requires interactive authentication. Follow these steps:

### Option 1: Via Railway Dashboard (Recommended)
1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository: `jeanpaul09/OracleX`
5. Railway will automatically detect Python and use the `railway.json` configuration
6. Add environment variables in the Railway dashboard under Variables

### Option 2: Via Railway CLI (Interactive)
```bash
npx @railway/cli login
npx @railway/cli init
npx @railway/cli up
```

### Configuration:
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Build**: Automatic via Nixpacks (detects Python from requirements.txt)
- **Config File**: `railway.json`

---

## Next Steps

1. **Connect Railway** (via dashboard - see above)
2. **Set Environment Variables** in both Vercel and Railway dashboards
3. **Test Deployments**:
   - Railway: Better for full Python app with all dependencies
   - Vercel: Consider for API-only deployment

---

## Environment Variables Needed

Add these in both Vercel and Railway dashboards:

```
# Polymarket API
POLYMARKET_API_KEY=your_key
POLYMARKET_PRIVATE_KEY=your_private_key

# Database
DATABASE_URL=your_database_url
REDIS_URL=your_redis_url

# LLM
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Twitter/X
TWITTER_BEARER_TOKEN=your_token
```

---

## Project Structure
- `main.py` - FastAPI entry point
- `vercel.json` - Vercel configuration
- `railway.json` - Railway configuration
- `requirements.txt` - Python dependencies
- `.vercelignore` - Files excluded from Vercel deployment

