# OracleX

## Connecting to GitHub, Vercel, and Railway

### GitHub Setup

1. **Create a new repository on GitHub:**
   - Go to https://github.com/new
   - Create a new repository (public or private)
   - Do NOT initialize with README, .gitignore, or license (we already have these)

2. **Connect your local repository:**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

### Vercel Setup

1. **Install Vercel CLI (if not already installed):**
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```

3. **Link your project:**
   ```bash
   vercel
   ```
   Follow the prompts to link your project.

4. **Connect to GitHub (via Vercel Dashboard):**
   - Go to https://vercel.com/dashboard
   - Click "Add New Project"
   - Import your GitHub repository
   - Vercel will automatically detect the framework and deploy

5. **Environment Variables:**
   - Add any environment variables in the Vercel dashboard under Project Settings → Environment Variables

### Railway Setup

1. **Install Railway CLI (if not already installed):**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway:**
   ```bash
   railway login
   ```

3. **Initialize Railway project:**
   ```bash
   railway init
   ```

4. **Connect to GitHub (via Railway Dashboard):**
   - Go to https://railway.app/dashboard
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will automatically detect the configuration

5. **Environment Variables:**
   - Add environment variables in the Railway dashboard under your project → Variables

### Quick Start Commands

```bash
# Initialize and push to GitHub
git add .
git commit -m "Initial commit"
git push -u origin main

# Deploy to Vercel
vercel --prod

# Deploy to Railway
railway up
```

## Notes

- Update `vercel.json` and `railway.json` based on your project's build and start commands
- Make sure your `package.json` has the correct `build` and `start` scripts
- Environment variables should be set in each platform's dashboard

