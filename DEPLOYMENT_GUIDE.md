# 🚀 Finance Dashboard - Complete Deployment Guide

## Overview
Your finance dashboard is now ready to be deployed on a complete pipeline:
- **GitHub** - Version control (already set up ✅)
- **Supabase** - PostgreSQL database (to set up)
- **Vercel** - Hosting & serverless functions (to connect)
- **GitHub Actions** - CI/CD automation (workflow created ✅)

---

## 🔐 SECRETS TO MANAGE

### Why NOT to commit secrets?
- **NEVER** commit credentials, API keys, or private tokens to GitHub
- GitHub has automated scanners that detect exposed secrets
- Anyone with repo access could compromise your data

### Solution: GitHub Secrets
All sensitive data is stored as encrypted secrets in GitHub and injected at runtime.

**Your secrets list:**
```
DATABASE_URL                    → Supabase PostgreSQL connection
DATABASE_USER                   → PostgreSQL username
DATABASE_PASSWORD               → PostgreSQL password
GOOGLE_SHEETS_URL              → Your Google Sheets URL
GOOGLE_OAUTH_CLIENT_SECRET     → Google OAuth credentials (JSON content)
GOOGLE_OAUTH_TOKEN             → Generated OAuth token (JSON content)
VERCEL_ORG_ID                  → Vercel organization ID
VERCEL_PROJECT_ID              → Vercel project ID
VERCEL_TOKEN                   → Vercel deployment token
```

---

## ✅ QUICK START CHECKLIST

### Phase 1: Supabase Setup (Database)
- [ ] Create Supabase account: https://supabase.com
- [ ] Create new project (region: close to you)
- [ ] Copy PostgreSQL connection string
- [ ] Run database migration (schema.sql)
- [ ] Test connection from local machine

### Phase 2: GitHub Secrets (Security)
- [ ] Go to: https://github.com/vivekjari/finance-dashboard/settings/secrets/actions
- [ ] Add all 9 secrets listed above
- [ ] Verify each secret is marked as ✓

### Phase 3: Vercel Deployment (Hosting)
- [ ] Create Vercel account: https://vercel.com
- [ ] Import GitHub repository
- [ ] Add environment variables from GitHub Secrets
- [ ] Deploy project
- [ ] Test API at: `https://your-project.vercel.app`

### Phase 4: CI/CD Automation (Optional but Recommended)
- [ ] GitHub Actions workflow is already created ✓
- [ ] Add Vercel secrets (VERCEL_ORG_ID, VERCEL_PROJECT_ID, VERCEL_TOKEN)
- [ ] Push to GitHub and watch automatic deployment

---

## 📊 DATA FLOW DIAGRAM

```
Google Sheets
     ↓
Local Machine
     ↓ (sync_sheets.py)
Supabase (PostgreSQL)
     ↑
Vercel API
     ↑
Frontend (dashboard/index.html)
```

**With CI/CD:**
```
Developer Push to GitHub
     ↓
GitHub Actions Trigger
     ↓
Run Tests & Sync
     ↓
Deploy to Vercel
     ↓
Sync Database
     ↓
Live App Updates
```

---

## 🔗 CONNECTIONS

### Supabase → Vercel
1. In Vercel project settings → Environment Variables
2. Add `DATABASE_URL` from Supabase
3. Vercel connects to Supabase on deployment

### GitHub → Vercel
1. In Vercel → Import from GitHub
2. Select repository
3. Auto-deploys on every push to `main`

### GitHub Secrets → CI/CD Workflow
1. `.github/workflows/deploy.yml` runs on push
2. Automatically reads all GitHub Secrets
3. Deploys to Vercel, syncs database

---

## 📝 SETUP INSTRUCTIONS (DETAILED)

### 1️⃣ SUPABASE SETUP

**Create Project:**
```
1. Visit https://supabase.com/auth/signup
2. Sign up with GitHub (recommended)
3. Create new project
4. Name: "finance-dashboard"
5. Set strong password (save it!)
6. Select region closest to you
7. Click "Create new project"
```

**Get Connection Details:**
```
1. Go to Project → Settings → Database
2. Under "Connection string", copy the PostgreSQL URL
3. Format: postgresql://postgres:[password]@[host]:[port]/postgres
4. This is your DATABASE_URL
```

**Migrate Database:**
```
Option A: Using psql (if PostgreSQL is installed)
$ psql "your_connection_string" -f database/schema.sql

Option B: Using Supabase SQL Editor
1. Go to Project → SQL Editor
2. Click "New query"
3. Copy entire contents of: database/schema.sql
4. Paste into editor
5. Click "Run"
```

**Verify Migration:**
```
$ psql "your_connection_string"
> \dt  # List all tables
> SELECT * FROM revenue_streams;  # Should return empty but valid
```

---

### 2️⃣ GITHUB SECRETS SETUP

**Go to Repository Settings:**
```
https://github.com/vivekjari/finance-dashboard/settings/secrets/actions
```

**Add Each Secret:**
```
1. Click "New repository secret"
2. Name: DATABASE_URL
3. Value: postgresql://postgres:[password]@[host]:[port]/postgres
4. Click "Add secret"

Repeat for all 9 secrets
```

**List of Secrets to Add:**

| # | Name | Value Source |
|---|------|--------------|
| 1 | DATABASE_URL | Supabase → Settings → Database |
| 2 | DATABASE_USER | postgres (from connection string) |
| 3 | DATABASE_PASSWORD | From Supabase password |
| 4 | GOOGLE_SHEETS_URL | Your Google Sheets link |
| 5 | GOOGLE_OAUTH_CLIENT_SECRET | Google Cloud Console |
| 6 | GOOGLE_OAUTH_TOKEN | Run: `python auth_google.py` locally |
| 7 | VERCEL_ORG_ID | Vercel → Account Settings → Teams |
| 8 | VERCEL_PROJECT_ID | Vercel project page |
| 9 | VERCEL_TOKEN | https://vercel.com/account/tokens |

---

### 3️⃣ VERCEL DEPLOYMENT

**Connect GitHub:**
```
1. Visit https://vercel.com
2. Click "Add New..." → "Project"
3. Click "Continue with GitHub"
4. Search "finance-dashboard"
5. Click "Import"
```

**Configure Build:**
```
Framework: Python (FastAPI)
Build Command: pip install -r requirements.txt
Install Command: pip install -r requirements.txt
Output Directory: (leave blank)
Root Directory: (leave blank)
```

**Add Environment Variables:**
```
1. Click "Environment Variables" tab
2. For each secret in GitHub, add:
   Name: [SECRET_NAME]
   Value: $GITHUB_SECRET_[NAME]  (or paste directly)
3. Click "Save"
```

**Deploy:**
```
1. Click "Deploy"
2. Wait for build (2-5 minutes)
3. Visit your live URL: https://[project-name].vercel.app
4. Check: https://[project-name].vercel.app/docs (API docs)
```

---

### 4️⃣ GITHUB ACTIONS CI/CD (OPTIONAL)

**Already Created:**
- Workflow file: `.github/workflows/deploy.yml`
- Triggers on: Every push to `main`

**What It Does:**
1. Pulls code from GitHub
2. Installs dependencies
3. Deploys to Vercel
4. Syncs database (optional)
5. Runs Google Sheets sync

**No additional setup needed!** Just push to GitHub and watch it auto-deploy.

---

## 🧪 TESTING YOUR SETUP

### Test 1: Local Database Connection
```bash
psql "your_supabase_connection_string"
\dt  # Should show all tables
\q   # Exit
```

### Test 2: Vercel API
```bash
curl https://your-project.vercel.app/docs
# Should return Swagger API documentation
```

### Test 3: GitHub Actions
```
1. Make a small change to any file
2. Push to GitHub
3. Go to: Actions tab
4. Watch the deploy workflow run
5. Check Vercel dashboard for deployment
```

---

## 🐛 TROUBLESHOOTING

### Problem: "No database found"
**Solution:** 
- Check DATABASE_URL is correct in Vercel env vars
- Verify Supabase project is running
- Test with: `psql "your_connection_string"`

### Problem: "Deployment failed on Vercel"
**Solution:**
- Check build logs: Vercel → Project → Deployments
- Verify all environment variables are set
- Check if Python version is compatible (3.9+)

### Problem: "GitHub Actions workflow not triggering"
**Solution:**
- Check workflow file syntax: `.github/workflows/deploy.yml`
- Verify secrets are added (9 total needed)
- Manually trigger: Actions tab → Deploy → "Run workflow"

### Problem: "Google Sheets sync not working"
**Solution:**
- Re-run: `python auth_google.py` locally
- Copy new token to GitHub Secret: `GOOGLE_OAUTH_TOKEN`
- Check Google Cloud credentials are valid

---

## 🎯 WHAT'S NEXT?

1. **Monitor** - Set up error alerts
2. **Scale** - Add more workers/database replicas
3. **Backup** - Enable Supabase automated backups
4. **Security** - Enable two-factor authentication on GitHub, Vercel, Supabase

---

## 📞 USEFUL LINKS

- Supabase Docs: https://supabase.com/docs
- Vercel Docs: https://vercel.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- GitHub Actions: https://docs.github.com/en/actions
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

**Created:** May 2, 2026
**Status:** Ready for deployment ✅
