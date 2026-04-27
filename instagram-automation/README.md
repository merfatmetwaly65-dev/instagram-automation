# AutoGram — Instagram Comment-to-DM Automation

A ManyChat-style tool that automatically replies to Instagram comments and sends DMs when a user comments a specific keyword on your posts.

---

## Features

- **Keyword triggers** — Detects configured keywords in comments (case-insensitive, partial match)
- **Auto comment reply** — Posts a public reply to matched comments
- **Auto DM** — Sends a private message to the commenter
- **Deduplication** — Never processes the same comment twice
- **Multi-campaign** — Multiple post/keyword combinations, all manageable from the dashboard
- **Webhook signature validation** — Verifies every incoming request using your App Secret

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/yourname/instagram-automation
cd instagram-automation
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
WEBHOOK_VERIFY_TOKEN=some_random_secret_you_choose
APP_SECRET=your_facebook_app_secret
DATABASE_URL=sqlite:///./instagram_automation.db
SECRET_KEY=another_random_string
```

### 3. Run

```bash
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Instagram API Setup (Step-by-Step)

### Step 1 — Convert your Instagram to a Business or Creator account

1. Open Instagram → **Settings** → **Account**
2. Tap **Switch to Professional Account**
3. Choose **Business** or **Creator**
4. Connect it to a **Facebook Page** (create one if needed)

---

### Step 2 — Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps** → **Create App**
3. Select **Business** as the app type
4. Fill in the name and contact email
5. Click **Create App**

---

### Step 3 — Add Instagram Graph API

1. In your new app's dashboard, click **Add Product**
2. Find **Instagram** and click **Set Up**
3. You'll see **Instagram Graph API** added to your left sidebar

---

### Step 4 — Add Required Permissions

1. Go to **App Review** → **Permissions and Features**
2. Request these permissions:
   - `instagram_manage_comments` — to reply to comments
   - `instagram_manage_messages` — to send DMs
   - `pages_manage_metadata` — for webhook subscriptions
3. For development/testing, you can use these in **Development Mode** without approval (only works for users added as testers/admins)

---

### Step 5 — Generate a Long-Lived User Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the dropdown
3. Click **Generate Access Token**
4. Grant the requested permissions (select `instagram_manage_comments`, `instagram_manage_messages`, `pages_read_engagement`)
5. Copy the short-lived token (valid 1 hour)

**Convert to a long-lived token (valid 60 days):**

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```

Save the returned `access_token`.

**Refreshing tokens before they expire:**  
Tokens last 60 days but reset if used within that window. To refresh programmatically:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=CURRENT_LONG_LIVED_TOKEN"
```

Set a calendar reminder at 50 days and run this command.

---

### Step 6 — Find Your Page ID and Instagram Business Account ID

In Graph API Explorer, run:

```
GET /me/accounts
```

Look for your page in the response. Copy the `id` field — that's your **Page ID**.

Then run:

```
GET /{page-id}?fields=instagram_business_account
```

The `id` inside `instagram_business_account` is your **Instagram Business Account ID**.

---

### Step 7 — Configure the Webhook

1. In your Facebook app, go to **Webhooks** in the left sidebar
2. Click **Add Subscription** → select **Instagram**
3. Set:
   - **Callback URL**: `https://your-app.railway.app/webhook/instagram`
   - **Verify Token**: the same value as `WEBHOOK_VERIFY_TOKEN` in your `.env`
4. Click **Verify and Save**
5. Subscribe to the `comments` field

> ⚠️ For local development, use [ngrok](https://ngrok.com): `ngrok http 8000` and use the HTTPS URL as your callback URL.

---

### Step 8 — Find a Post ID

In Graph API Explorer:

```
GET /{instagram-business-account-id}/media?fields=id,caption,thumbnail_url,timestamp
```

This lists your recent posts. Copy the `id` of the post you want to track.

---

## Dashboard Usage

### Settings Tab
Enter your credentials (Access Token, Page ID, Instagram Account ID) and click **Save & Verify**. The app will confirm your token works.

### Campaigns Tab
- Click **New Campaign** to create an automation
- Paste a Post ID — it auto-fetches the post preview on blur
- Add comma-separated trigger keywords (e.g. `free, send me, info, link`)
- Write the comment reply and DM message
- Toggle campaigns on/off without deleting them

---

## Deployment

### Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables (from `.env`) in Railway's Variables tab
4. Railway auto-detects the `Dockerfile` and deploys

### Render

```bash
# Push to GitHub, then connect on render.com
# render.yaml is pre-configured
```

### Docker (self-host)

```bash
docker build -t instagram-automation .
docker run -d \
  -p 8000:8000 \
  -v /path/to/data:/data \
  -e WEBHOOK_VERIFY_TOKEN=your_token \
  -e APP_SECRET=your_secret \
  instagram-automation
```

---

## Project Structure

```
├── main.py              # FastAPI app entry point
├── instagram.py         # Instagram Graph API client (with retry/backoff)
├── models.py            # SQLAlchemy models (Config, Campaign, ProcessedComment)
├── database.py          # DB session setup
├── routes/
│   ├── webhook.py       # Webhook verification + event handling
│   ├── dashboard.py     # Serves the HTML dashboard
│   └── api.py           # REST API for campaigns/config/stats
├── templates/
│   └── dashboard.html   # Full single-page dashboard UI
├── static/              # (reserved for additional static files)
├── .env.example
├── Dockerfile
├── railway.toml
├── render.yaml
└── requirements.txt
```

---

## Security Notes

- Webhook signature is validated using `X-Hub-Signature-256` and your `APP_SECRET` on every incoming request
- Credentials are never exposed in the frontend (token preview is truncated)
- All secrets are loaded from `.env` — never hardcoded
- Deduplication prevents double-firing on repeated webhook deliveries

---

## Migrating to PostgreSQL

Change `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Remove `aiosqlite` and add `psycopg2-binary` to `requirements.txt`. No code changes needed.
