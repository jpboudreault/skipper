# 🚀 Skipper Deployment Guide (Fly.io)

Deploy **Skipper** to [Fly.io](https://fly.io) as a single unified container (FastAPI + SvelteKit).

> **Windows/WSL:** Run all commands in WSL.

## Prerequisites

- [Fly.io account](https://fly.io)
- [Google Cloud Console](https://console.cloud.google.com) OAuth 2.0 Web Client ID

---

## Step 1: Configure teams and admins

1. Copy the tenants template:
   ```bash
   cp backend/app/tenants.json.example backend/app/tenants.json
   ```
2. Edit `backend/app/tenants.json` — set team names, seasons, and `admin_emails` for each team.
   Optional: enable Spordle sync per team — see [`docs/league-integrations.md`](docs/league-integrations.md).
3. Only emails listed in `admin_emails` can log in when `DEV_MODE=false`.

## Step 2: Choose a unique app name

1. Open [`fly.toml`](./fly.toml) — the `app` value is a placeholder.
2. Set `FLY_APP_NAME` in `backend/.env` (copy from `backend/.env.dist`):
   ```bash
   FLY_APP_NAME=your-unique-app-name
   ```

## Step 3: Install flyctl (WSL)

```bash
curl -L https://fly.io/install.sh | sh
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"
fly auth login
```

## Step 4: Create app and persistent volume

SQLite data lives on a Fly volume:

```bash
fly apps create your-unique-app-name
fly volumes create skipper_data --region yyz --size 1 --app your-unique-app-name
```

## Step 5: Set production secrets

```bash
fly secrets set \
  JWT_SECRET="$(openssl rand -hex 32)" \
  GOOGLE_CLIENT_ID="your_google_client_id" \
  DEV_MODE="false" \
  --app your-unique-app-name
```

In Google Cloud Console, add your production URL (e.g. `https://your-unique-app-name.fly.dev`) to **Authorized JavaScript Origins**.

Optional — scoresheet photo ingestion:
```bash
fly secrets set ANTHROPIC_API_KEY="your_key" --app your-unique-app-name
```

Optional — single-language deployment (hide the EN/FR picker and lock UI + API errors):
```bash
# French-only example
fly secrets set SKIPPER_LOCALE="fr" --app your-unique-app-name

# Or set in fly.toml [env] instead of secrets (en or fr)
```

When `SKIPPER_LOCALE` is unset, the app stays bilingual with browser default + language picker (default).

## Step 6: Back up before you deploy

Production data lives on the Fly volume (`/data/database.db`), not in the container image. A normal deploy keeps that data, but you should still back up before risky changes.

`backup_db.sh` reads `FLY_APP_NAME` from `backend/.env` (same as `deploy.sh`) and saves a timestamped copy under `backup_private/`. That folder is gitignored — backups are never committed.

```bash
# Download the live database
bash backup_db.sh

# Optional: also create an on-demand Fly volume snapshot
bash backup_db.sh --snapshot
```

List existing Fly snapshots:

```bash
fly volumes list --app your-unique-app-name
fly volumes snapshots list VOLUME_ID --app your-unique-app-name
```

## Step 7: Deploy

Back up first, then deploy:

```bash
bash backup_db.sh
bash deploy.sh
```

---

## Post-deployment

### Bootstrap data

Log in, then seed players and games. See [`bootstrap/README.md`](./bootstrap/README.md).

```bash
export SKIPPER_URL="https://your-unique-app-name.fly.dev"
export TOKEN="your_jwt_token_here"

curl -X POST "$SKIPPER_URL/api/players/" \
  -H "Content-Type: application/json" \
  -H "X-Active-Team-ID: 1" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Babe", "last_name": "Ruth", "jersey": 3, "active": true}'
```

### View logs

```bash
fly logs --app your-unique-app-name
```

### SSH into container

```bash
fly ssh console --app your-unique-app-name
```

---

## Local vs production

| Variable | Local (`DEV_MODE=true`) | Production |
|----------|-------------------------|------------|
| `JWT_SECRET` | Optional (default ok) | **Required** — use `openssl rand -hex 32` |
| `GOOGLE_CLIENT_ID` | Required for login | Required for login |
| `DEV_MODE` | `true` — auto-creates users | `false` — only `tenants.json` emails allowed |
| `FLY_APP_NAME` | Used by `deploy.sh` and `backup_db.sh` | Used by `deploy.sh` and `backup_db.sh` |
