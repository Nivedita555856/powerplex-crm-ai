# PowerPlex CRM AI — Deployment Guide

Two deployment options are supported:

| Option | What you get | When to use |
|--------|-------------|-------------|
| **Render only** | Single URL serves both API + UI | Simplest — recommended |
| **Render + Vercel** | Vercel for UI, Render for API | If you want a custom domain on Vercel |

---

## Option A — Render only (recommended)

### Step 1 — Push to GitHub

```bash
cd C:\Users\admin\ProITBridge\crm-ai

git init                        # if not already a repo
git add .
git commit -m "deploy: powerplex crm ai"

# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/powerplex-crm-ai.git
git push -u origin main
```

> Make sure `.env` is in `.gitignore` (it is). Your secrets stay local.

---

### Step 2 — Create a Render Web Service

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub account and select the `powerplex-crm-ai` repo
3. Render will auto-detect `render.yaml` — click **Apply**

   If it doesn't auto-detect, set manually:
   - **Environment**: Python
   - **Build command**: `pip install --upgrade pip && pip install -r requirements.txt && python scripts/prestart.py`
   - **Start command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

---

### Step 3 — Set Environment Variables

In your Render service → **Environment** tab, add these secrets:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | your Groq API key from console.groq.com |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | your Gmail App Password (16 chars) |
| `ADMIN_EMAIL` | your Gmail address (BCC for all emails) |

Everything else already has correct defaults in `render.yaml`.

---

### Step 4 — Deploy

Click **Deploy**. The build takes ~5–8 minutes (sentence-transformers model download).

Once live your app is at:
```
https://powerplex-crm-ai.onrender.com
```

> **Free tier note**: Render free services spin down after 15 min of inactivity. The first request after sleep takes ~30 seconds to wake up. This is normal.

---

## Option B — Render (API) + Vercel (Frontend)

Use this if you want a Vercel URL for the UI with a custom domain.

### Step 1 — Deploy backend on Render

Follow Option A steps 1–4 above. Your Render URL will be:
```
https://powerplex-crm-ai.onrender.com
```

### Step 2 — Update vercel.json

Open `vercel.json` and confirm the Render URL matches:
```json
{ "source": "/api/(.*)", "destination": "https://powerplex-crm-ai.onrender.com/api/$1" }
```

### Step 3 — Update index.html api-base

Open `frontend/index.html` and set the meta tag to your Render URL:
```html
<meta name="api-base" content="https://powerplex-crm-ai.onrender.com">
```

Commit and push this change.

### Step 4 — Deploy frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New → Project**
2. Import the same GitHub repo
3. Set:
   - **Framework Preset**: Other
   - **Root directory**: `frontend`
   - **Output directory**: `.` (dot)
   - **Build command**: *(leave empty)*
4. Click **Deploy**

Your frontend is now at `https://your-project.vercel.app`.

---

## Verify the deployment

Once deployed, test these URLs in your browser:

```
GET  https://powerplex-crm-ai.onrender.com/api/health     → {"status":"ok",...}
GET  https://powerplex-crm-ai.onrender.com/api/customers  → [...customers...]
GET  https://powerplex-crm-ai.onrender.com/               → PowerPlex CRM UI
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Build fails on `sentence-transformers` | Render free tier has 512 MB RAM — if OOM, downgrade to `sentence-transformers==2.7.0` |
| `ModuleNotFoundError: crewai` | Already commented out in requirements.txt ✓ |
| Chat returns 500 errors | Check Render logs → confirm `GROQ_API_KEY` is set |
| Emails not sending | Confirm `SMTP_PASSWORD` is the Gmail **App Password** (16 chars, no spaces) |
| Render spins down too fast | Upgrade to Render Starter ($7/mo) for always-on |
| Vercel shows blank page | Confirm `api-base` meta tag is set in index.html |
