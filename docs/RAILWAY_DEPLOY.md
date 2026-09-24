# Railway deployment

KOVA is already wired for Railway via Nixpacks (`nixpacks.toml`), `Procfile`, `railway.toml`, `release.sh`, and `start.sh`.

Target repo: [unimart831-ai/KOVA](https://github.com/unimart831-ai/KOVA)

## 1. Create the Railway project

1. New project → **Deploy from GitHub** → select `unimart831-ai/KOVA`.
2. Root directory: repo root (this folder — where `manage.py` lives).
3. Add plugins / services:
   - **PostgreSQL**
   - **Redis**
4. Duplicate the web service (or add empty services) for:
   - **web** — uses `Procfile` `web` (`bash start.sh`)
   - **worker** — `Procfile` `worker` (Celery)
   - **beat** — `Procfile` `beat` (Celery Beat)

Railway Nixpacks detects Python + Node and runs the build commands in `nixpacks.toml` (Tailwind CSS + chmod scripts).

## 2. Required environment variables

Set on **every** service that runs Django/Celery (`web`, `worker`, `beat`):

| Variable | Notes |
|----------|--------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` (also set in Nixpacks) |
| `SECRET_KEY` | Strong random; never the insecure default |
| `FIELD_ENCRYPTION_KEY` | Fernet key, **separate** from `SECRET_KEY` |
| `DATABASE_URL` | Auto from Postgres plugin |
| `REDIS_URL` | Auto from Redis plugin (Celery + Channels) |
| `ALLOWED_HOSTS` | Your Railway domain + custom domain if any |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.up.railway.app` (+ custom) |
| `SITE_URL` | Public HTTPS origin |
| `SITE_DOMAIN` | Host only (used by `start.sh` Sites framework) |
| `SITE_NAME` | e.g. `Kova Agent` |

Generate encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Strongly recommended

| Variable | Purpose |
|----------|---------|
| `SKIP_STARTUP_MIGRATE` | **Do not set.** Web `start.sh` always migrates so login works even if release skipped. |
| `AWS_STORAGE_BUCKET_NAME` | Cloudflare R2 bucket |
| `AWS_S3_ENDPOINT_URL` | R2 endpoint |
| `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` | R2 credentials |
| `SENTRY_DSN` | Error monitoring |
| `RESEND_API_KEY` | Transactional email (optional to boot; console fallback until set) |
| `DEFAULT_FROM_EMAIL` | e.g. `Kova Agent <noreply@yourdomain.com>` |
| `OPENROUTER_API_KEY` (or OpenAI/Anthropic) | LLM |
| Meta / WhatsApp / M-Pesa keys | See `.env.example` and platform setup docs |

`production.py` **refuses to boot** without a real `SECRET_KEY` and `FIELD_ENCRYPTION_KEY`.

## 3. What runs on deploy

1. **Build** — Nixpacks: apt deps, `pip install`, `npm install`, Tailwind minify, `chmod +x start.sh release.sh`
2. **Release** (`railway.toml` → `bash release.sh`) — `migrate` + prune stale Celery beat tasks
3. **Web start** (`start.sh`) — collectstatic, optional migrate, seed reel beds, ensure superuser, Daphne on `$PORT`
4. **Worker / beat** — Celery as in `Procfile`

Health endpoint: `GET /health/` (plain `ok`).

## 4. Post-deploy checklist

- [ ] Open `https://YOUR-APP.up.railway.app/health/` → `ok`
- [ ] Landing `/` and `/pricing/` load with CSS
- [ ] Admin login works (superuser from `DJANGO_SUPERUSER_*` if set — see `create_superuser` command)
- [ ] Celery worker logs show connected to Redis
- [ ] Upload a media file and confirm it lands in R2 (not ephemeral disk)
- [ ] Set `CUSTOM_DOMAIN` if using a custom host

## 5. Local reference

Full variable list: `.env.example`.  
Docker Compose (local Postgres/Redis): `docker-compose.yml`.
